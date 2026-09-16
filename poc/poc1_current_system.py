"""First POC: read the journal and print the commander's current system.

Run from the project root:

    python poc/poc1_current_system.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_finder.config import get_journal_dir
from codex_finder.journal import find_current_system


def main() -> int:
    journal_dir = get_journal_dir()
    if not journal_dir.is_dir():
        print(f"Journal directory not found: {journal_dir}", file=sys.stderr)
        return 2
    location = find_current_system(journal_dir)
    if location is None:
        print("No current system found in the journal.", file=sys.stderr)
        return 1
    print(f"Current system: {location.system}  (as of {location.timestamp})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
