"""Configuration and category definitions for codex-finder.

Everything that is environment- or deployment-specific lives here so the rest of
the code can stay portable.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Journal location
# ---------------------------------------------------------------------------
# Path to the Elite Dangerous journal directory. On a native Windows install
# this is typically:
#   C:\Users\<name>\Saved Games\Frontier Developments\Elite Dangerous
# The default below matches the developer's WSL mount. Override at runtime with
# the CODEX_FINDER_JOURNAL_DIR environment variable or the --journal-dir flag.
DEFAULT_JOURNAL_DIR = Path(
    "/mnt/c/Users/vladi/Saved Games/Frontier Developments/Elite Dangerous"
)


def get_journal_dir() -> Path:
    """Resolve the journal directory (env var wins over the default)."""
    env = os.environ.get("CODEX_FINDER_JOURNAL_DIR")
    return Path(env).expanduser() if env else DEFAULT_JOURNAL_DIR


# ---------------------------------------------------------------------------
# Spansh API
# ---------------------------------------------------------------------------
SPANSH_BASE_URL = "https://spansh.co.uk"
SPANSH_SEARCH_URL = f"{SPANSH_BASE_URL}/api/bodies/search"
SPANSH_FIELD_VALUES_URL = f"{SPANSH_BASE_URL}/api/bodies/field_values"

# Be a good citizen: never exceed one request per second (per spansh_api.md).
SPANSH_MIN_REQUEST_INTERVAL = 1.1  # seconds
USER_AGENT = "codex-finder/0.1 (+https://github.com/; Elite Dangerous codex helper)"

# Cache for the (large, slow-changing) list of landmark subtypes.
CACHE_DIR = Path(
    os.environ.get("CODEX_FINDER_CACHE_DIR", Path.home() / ".cache" / "codex-finder")
)
CACHE_TTL_SECONDS = 7 * 24 * 3600  # one week

# ---------------------------------------------------------------------------
# Codex categories
# ---------------------------------------------------------------------------
# The user-facing categories and the aliases accepted on the command line.
CATEGORY_BIOLOGY = "biology"
CATEGORY_CLOUD = "cloud"
CATEGORY_ANOMALIES = "anomalies"

CATEGORY_ALIASES = {
    "biology": CATEGORY_BIOLOGY,
    "bio": CATEGORY_BIOLOGY,
    "cloud": CATEGORY_CLOUD,
    "clouds": CATEGORY_CLOUD,
    "anomaly": CATEGORY_ANOMALIES,
    "anomalies": CATEGORY_ANOMALIES,
}

CATEGORIES = (CATEGORY_BIOLOGY, CATEGORY_CLOUD, CATEGORY_ANOMALIES)

# Spansh subtype tokens that belong to the Codex "Cloud" hierarchy. In-game
# this includes Lagrange clouds as well as nested Mollusc, Gyre Pod and crystal
# entries found inside clouds.
CLOUD_TYPES = frozenset(
    {
        "Aster",
        "Chalice Pod",
        "Calcite Plates",
        "Cloud",
        "Collared Pod",
        "Gyre Pod",
        "Gyre",
        "Ice Crystals",
        "Lagrange Cloud",
        "Metallic Crystals",
        "Mineral Spheres",
        "Mollusc",
        "Peduncle",
        "Quadripartite",
        "Rhizome",
        "Silicate Crystals",
        "Stolon",
        "Storm Cloud",
        "Void",
    }
)

# Spansh "landmark type" tokens that represent biological (Codex "Organic
# Structures") life forms. A landmark subtype belongs to Biology when its name
# contains one of these tokens. Derived from the live Spansh
# /field_values/landmark_type list, with geology, Guardian, Thargoid and
# man-made structures excluded.
BIOLOGY_TYPES = frozenset(
    {
        "Aleoida",
        "Amphora Plant",
        "Anemone",
        "Aster",
        "Bacterium",
        "Bark Mounds",
        "Brain Tree",
        "Cactoida",
        "Chalice Pod",
        "Clypeus",
        "Collared Pod",
        "Concha",
        "Coral Tree",
        "Crystalline Shard",
        "Electricae",
        "Fonticulua",
        "Frutexa",
        "Fumerola",
        "Fungoida",
        "Gyre",
        "Osseus",
        "Peduncle",
        "Quadripartite",
        "Recepta",
        "Rhizome",
        "Shards",
        "Stolon",
        "Stratum",
        "Toughened Spear Roots",
        "Tubers",
        "Tubus",
        "Tussock",
    }
)

# Biology genera (Spansh landmark "type" values) whose Codex entries come in
# colour variants. When Spansh reports one of these without a colour the data is
# simply incomplete, so such landmarks are omitted rather than shown colourless.
# Genera not listed here (e.g. Tubers, Bark Mounds) have a single Codex
# entry and no colour.
COLOUR_VARIANT_TYPES = frozenset(
    {
        "Aleoida",
        "Bacterium",
        "Cactoida",
        "Clypeus",
        "Concha",
        "Electricae",
        "Fonticulua",
        "Frutexa",
        "Fumerola",
        "Fungoida",
        "Osseus",
        "Recepta",
        "Stratum",
        "Tubus",
        "Tussock",
    }
)

# How many nearest systems to report.
TOP_N_SYSTEMS = 10

# Default search radius (light years) when --within is not supplied. Biology is
# common and dense, so a tight radius keeps it fast; clouds and anomalies are
# rare and need a galaxy-wide search.
DEFAULT_WITHIN_LY = {
    CATEGORY_BIOLOGY: 500.0,
    CATEGORY_CLOUD: 10000.0,
    CATEGORY_ANOMALIES: 10000.0,
}
