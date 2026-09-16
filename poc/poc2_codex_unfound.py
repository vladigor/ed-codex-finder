"""Second POC: list Cloud Codex entries the commander has NOT yet found.

This reads the journal to work out which Cloud entries are already logged, then
fetches the full Cloud universe from Spansh and prints the difference.

    python poc/poc2_codex_unfound.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_finder.config import CATEGORY_CLOUD, get_journal_dir
from codex_finder.finder import category_universe
from codex_finder.journal import find_found_entries
from codex_finder.spansh import SpanshClient, SpanshError


def main() -> int:
    journal_dir = get_journal_dir()
    if not journal_dir.is_dir():
        print(f"Journal directory not found: {journal_dir}", file=sys.stderr)
        return 2

    found = find_found_entries(journal_dir, CATEGORY_CLOUD)
    print(f"Cloud entries already found: {len(found)}")
    for name in sorted(found):
        print(f"  [x] {name}")

    try:
        universe = category_universe(SpanshClient(), CATEGORY_CLOUD)
    except SpanshError as exc:
        print(f"Could not fetch Cloud universe from Spansh: {exc}", file=sys.stderr)
        return 1

    missing = sorted(universe - found)
    print()
    print(f"Cloud entries NOT yet found: {len(missing)}")
    for name in missing:
        print(f"  [ ] {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
