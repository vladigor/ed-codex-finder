"""Reading the Elite Dangerous player journal.

The journal is a directory of ``Journal.*.log`` files. Each line is a single
JSON object describing one game event. We only need two things from it:

* the commander's current star system, and
* the set of Codex entries they have already discovered.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from . import codex

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
