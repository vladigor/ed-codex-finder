"""Classification of Codex entries / Spansh landmark subtypes into categories.

The three user-facing categories are ``biology``, ``cloud`` and ``anomalies``.
A single classification rule is used everywhere so the journal side and the
Spansh side agree on what belongs to a category.
"""

from __future__ import annotations

from . import config


def normalise_category(name: str) -> str:
    """Map a user-supplied category name to a canonical category key.

    Raises ``ValueError`` for anything unrecognised.
    """
    key = config.CATEGORY_ALIASES.get(name.strip().lower())
    if key is None:
        valid = ", ".join(config.CATEGORIES)
        raise ValueError(f"Unknown category {name!r}. Choose one of: {valid}.")
    return key


def classify_subtype(subtype: str) -> str | None:
    """Return the category for a Spansh landmark subtype, or ``None`` to ignore.

    ``subtype`` is a value such as ``"Bacterium Aurasus"``,
    ``"Caeruleum Lagrange Cloud"`` or ``"E04-Type Anomaly"``.
    """
    if "Anomaly" in subtype:
        return config.CATEGORY_ANOMALIES
    if "Cloud" in subtype:
        return config.CATEGORY_CLOUD
    for token in config.BIOLOGY_TYPES:
        if token in subtype:
            return config.CATEGORY_BIOLOGY
    return None


def entry_key(name: str) -> str:
    """Canonical key for a Codex entry as it appears in the journal.

    Biology names already carry the colour variant (for example
    ``"Aleoida Arcus - Emerald"``); cloud and anomaly names have none. Spansh
    exposes the same colour via each landmark's ``variant`` field, so we keep the
    full name and compare at the species+colour level - see
    :func:`spansh_entry_key`.
    """
    return name.strip()


def spansh_entry_key(subtype: str, variant: str | None) -> str:
    """Build the entry key for a Spansh landmark, matching journal naming.

    Biology landmarks have a colour ``variant`` (``"Bacterium Aurasus"`` +
    ``"Green"`` -> ``"Bacterium Aurasus - Green"``). Clouds, anomalies and the
    Horizons organics without a colour have no variant, so the subtype is used
    verbatim.
    """
    return f"{subtype} - {variant}" if variant else subtype

