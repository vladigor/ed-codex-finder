"""Command line interface for codex-finder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config
from .codex import normalise_category
from .finder import SystemResult, find_new_codex_bodies
from .journal import find_current_system, find_found_entries
from .spansh import SpanshClient, SpanshError


def _parse_distance(value: str) -> float:
    """Parse a light-year distance like ``400`` or ``400ly``."""
    text = value.strip().lower().removesuffix("ly").strip()
    try:
        distance = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid distance: {value!r}")
    if distance <= 0:
        raise argparse.ArgumentTypeError("distance must be greater than 0")
    return distance


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-finder",
        description=(
            "Find Elite Dangerous Codex entries you have not discovered yet, "
            "ordered by distance from your current system."
        ),
    )
    parser.add_argument(
        "category",
        help="Codex category to search: biology, cloud or anomalies.",
    )
    parser.add_argument(
        "--journal-dir",
        type=Path,
        default=None,
        help="Override the Elite Dangerous journal directory.",
    )
    parser.add_argument(
        "--nearest",
        type=int,
        default=config.TOP_N_SYSTEMS,
        help=f"Number of systems to show (default {config.TOP_N_SYSTEMS}).",
    )
    parser.add_argument(
        "--within",
        type=_parse_distance,
        default=None,
        metavar="LY",
        help=(
            "Only search within this many light years (e.g. 400 or 400ly). "
            "Defaults to 500ly for biology, 10000ly otherwise."
        ),
    )
    return parser


def _print_results(
    category: str,
    system: str,
    found_count: int,
    results: list[SystemResult],
    max_distance: float | None = None,
) -> None:
    print(f"Current system: {system}")
    print(f"Category: {category} ({found_count} entries already in your journal)")
    print()
    if not results:
        if max_distance is not None:
            print(
                f"No bodies with new Codex entries were found within "
                f"{max_distance:,.0f} ly."
            )
        else:
            print("No nearby bodies with new Codex entries were found.")
        return
    print(f"Nearest systems with new {category} Codex entries:")
    print()
    for index, result in enumerate(results, start=1):
        print(f"{index:2}. {result.system}  ({result.distance:,.0f} ly)")
        for entry in sorted(result.new_entries):
            body = result.new_entries[entry]
            print(f"      - {entry}  [{body}]")
        print()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        category = normalise_category(args.category)
    except ValueError as exc:
        parser.error(str(exc))

    journal_dir = args.journal_dir or config.get_journal_dir()
    if not journal_dir.is_dir():
        print(f"Journal directory not found: {journal_dir}", file=sys.stderr)
        return 2

    location = find_current_system(journal_dir)
    if location is None:
        print("Could not determine your current system from the journal.", file=sys.stderr)
        return 2

    found = find_found_entries(journal_dir, category)

    max_distance = args.within
    if max_distance is None:
        max_distance = config.DEFAULT_WITHIN_LY[category]

    client = SpanshClient()
    try:
        results = find_new_codex_bodies(
            client,
            reference_system=location.system,
            reference_coords=location.star_pos,
            category=category,
            found=found,
            top_n=args.nearest,
            max_distance=max_distance,
        )
    except SpanshError as exc:
        print(f"Spansh query failed: {exc}", file=sys.stderr)
        return 1

    _print_results(category, location.system, len(found), results, max_distance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
