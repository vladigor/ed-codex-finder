"""Core logic: find nearby bodies with Codex entries the commander lacks."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import codex, config
from .spansh import SpanshClient

# Safety cap so a broad search cannot page forever.
_MAX_PAGES = 15
_PAGE_SIZE = 50


@dataclass
class SystemResult:
    system: str
    distance: float
    new_entries: dict[str, str] = field(default_factory=dict)
    # new_entries maps entry name -> nearest body it was seen on.


def category_universe(client: SpanshClient, category: str) -> set[str]:
    """All landmark subtypes that belong to ``category`` (per Spansh's catalogue)."""
    return {
        subtype
        for subtype in client.landmark_subtypes()
        if codex.classify_subtype(subtype) == category
    }


def find_new_codex_bodies(
    client: SpanshClient,
    *,
    reference_system: str,
    category: str,
    found: set[str],
    top_n: int = config.TOP_N_SYSTEMS,
    max_distance: float | None = None,
) -> list[SystemResult]:
    """Return up to ``top_n`` nearest systems that hold new Codex entries.

    ``found`` is the set of entry keys the commander already has for ``category``.
    ``max_distance`` (light years) caps the search radius when given.
    """
    universe = category_universe(client, category)
    if category == config.CATEGORY_BIOLOGY:
        # Biology is tracked per colour variant, which Spansh returns on each
        # landmark. A species is worth querying whenever any of its colours might
        # be missing, so we query the whole species universe and filter variants
        # per body below.
        wanted = sorted(universe)
    else:
        # Cloud and anomaly entries have no colour, so a found subtype is done.
        wanted = sorted(universe - found)
    if not wanted:
        return []

    systems: dict[str, SystemResult] = {}
    order: list[str] = []

    for page in range(_MAX_PAGES):
        response = client.search_bodies(
            reference_system=reference_system,
            landmark_subtypes=wanted,
            max_distance=max_distance,
            size=_PAGE_SIZE,
            page=page,
        )
        results = response.get("results", [])
        if not results:
            break

        for body in results:
            system_name = body.get("system_name")
            if not system_name:
                continue
            distance = float(body.get("distance", 0.0))
            body_name = body.get("name", "")

            # Deduplicate the repeated landmark instances and keep only entries
            # of this category (including colour variant) that are still missing.
            new_here: set[str] = set()
            for lm in body.get("landmarks", []):
                subtype = lm.get("subtype")
                if subtype not in universe:
                    continue
                variant = lm.get("variant")
                # A colour-variant species with no colour recorded is incomplete
                # Spansh data, not a distinct Codex entry, so skip it.
                if variant is None and lm.get("type") in config.COLOUR_VARIANT_TYPES:
                    continue
                new_here.add(codex.spansh_entry_key(subtype, variant))
            new_here -= found
            if not new_here:
                continue

            entry = systems.get(system_name)
            if entry is None:
                if len(order) >= top_n:
                    # Already have enough nearer systems; this one is farther.
                    continue
                entry = SystemResult(system=system_name, distance=distance)
                systems[system_name] = entry
                order.append(system_name)
            for key in new_here:
                entry.new_entries.setdefault(key, body_name)

        if len(order) >= top_n:
            break
        if page + 1 >= response.get("count", 0) / _PAGE_SIZE:
            break

    ordered = [systems[name] for name in order]
    ordered.sort(key=lambda r: r.distance)
    return ordered[:top_n]
