"""Reading the Elite Dangerous player journal.

The journal is a directory of ``Journal.*.log`` files. Each line is a single
JSON object describing one game event. We only need two things from it:

* the commander's current star system, and
* the set of Codex entries they have already discovered.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from . import codex, config

# Events that record the system the commander is in.
_LOCATION_EVENTS = frozenset({"FSDJump", "Location", "CarrierJump"})

# Modern journals are named ``Journal.YYYY-MM-DDTHHMMSS.<part>.log``. Legacy
# (pre-Odyssey) journals use ``Journal.YYMMDDHHMMSS.<part>.log`` and are ignored
# because their numeric names sort after the ISO names and describe an old game
# version.
_ISO_JOURNAL_RE = re.compile(
    r"^Journal\.\d{4}-\d{2}-\d{2}T\d{6}\.\d+\.log$"
)


@dataclass(frozen=True)
class CurrentLocation:
    system: str
    timestamp: str
    star_pos: tuple[float, float, float] | None = None


def _star_pos(event: dict) -> tuple[float, float, float] | None:
    value = event.get("StarPos")
    if not isinstance(value, list) or len(value) != 3:
        return None
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError):
        return None


def _journal_files(journal_dir: Path) -> list[Path]:
    """Return modern ISO-named journal files, newest first."""
    files = [
        path
        for path in journal_dir.glob("Journal.*.log")
        if _ISO_JOURNAL_RE.match(path.name)
    ]
    return sorted(files, reverse=True)


def _iter_events(path: Path) -> Iterator[dict]:
    """Yield parsed JSON events from a single journal file, skipping bad lines."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    # Journals can be truncated mid-write while the game runs.
                    continue
    except OSError:
        return


def find_current_system(journal_dir: Path) -> CurrentLocation | None:
    """Find the most recent star system the commander was in.

    Files are scanned newest first; within a file we take the last location
    event. The first file that contains one wins, since filenames sort by time.
    """
    for path in _journal_files(journal_dir):
        latest: CurrentLocation | None = None
        for event in _iter_events(path):
            if event.get("event") in _LOCATION_EVENTS and event.get("StarSystem"):
                latest = CurrentLocation(
                    system=event["StarSystem"],
                    timestamp=event.get("timestamp", ""),
                    star_pos=_star_pos(event),
                )
        if latest is not None:
            return latest
    return None


def find_found_entries(journal_dir: Path, category: str) -> set[str]:
    """Return the set of normalised Codex entry keys already found for a category.

    Every journal file is scanned because discoveries accumulate over the whole
    history of play.
    """
    found: set[str] = set()
    for path in _journal_files(journal_dir):
        for event in _iter_events(path):
            if event.get("event") != "CodexEntry":
                continue
            name = event.get("Name_Localised") or event.get("Name")
            if not name:
                continue
            subtype = _codex_name_to_subtype(name)
            if codex.classify_subtype(subtype) != category:
                continue
            found.add(codex.entry_key(name))
    return found


def _codex_name_to_subtype(name: str) -> str:
    """Reduce a Codex localised name to the form used for classification.

    Biology names carry a region colour suffix ("Bacterium Aurasus - Green")
    which we drop so classification matches Spansh subtypes.
    """
    return name.split(" - ", 1)[0].strip()


@dataclass
class _FileContribution:
    """What one journal file contributes: found entries and its last location."""

    found: dict[str, set[str]]
    last_location: CurrentLocation | None


@dataclass
class JournalState:
    current: CurrentLocation | None
    found: dict[str, set[str]]


class JournalCache:
    """Scans the journal once and memoises each file by (mtime, size).

    Repeated scans only re-parse files that changed, which in practice is just
    the journal file the game is currently appending to. A single pass builds
    the found sets for every category and the current system, so callers do not
    re-read the whole history per request.
    """

    def __init__(self, journal_dir: Path) -> None:
        self._journal_dir = journal_dir
        self._cache: dict[Path, tuple[float, int, _FileContribution]] = {}
        self._lock = threading.Lock()

    def scan(self) -> JournalState:
        with self._lock:
            found: dict[str, set[str]] = {cat: set() for cat in config.CATEGORIES}
            current: CurrentLocation | None = None
            for path in _journal_files(self._journal_dir):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                cached = self._cache.get(path)
                if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
                    contribution = cached[2]
                else:
                    contribution = self._parse_file(path)
                    self._cache[path] = (stat.st_mtime, stat.st_size, contribution)
                for cat in config.CATEGORIES:
                    found[cat] |= contribution.found[cat]
                location = contribution.last_location
                if location and (current is None or location.timestamp > current.timestamp):
                    current = location
            return JournalState(current=current, found=found)

    @staticmethod
    def _parse_file(path: Path) -> _FileContribution:
        found: dict[str, set[str]] = {cat: set() for cat in config.CATEGORIES}
        last_location: CurrentLocation | None = None
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    # Cheap pre-filter: skip the vast majority of events without
                    # paying for a JSON parse.
                    if '"StarSystem"' not in line and '"CodexEntry"' not in line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    event_type = event.get("event")
                    if event_type in _LOCATION_EVENTS and event.get("StarSystem"):
                        last_location = CurrentLocation(
                            system=event["StarSystem"],
                            timestamp=event.get("timestamp", ""),
                            star_pos=_star_pos(event),
                        )
                    elif event_type == "CodexEntry":
                        name = event.get("Name_Localised") or event.get("Name")
                        if not name:
                            continue
                        category = codex.classify_subtype(_codex_name_to_subtype(name))
                        if category in found:
                            found[category].add(codex.entry_key(name))
        except OSError:
            pass
        return _FileContribution(found=found, last_location=last_location)

