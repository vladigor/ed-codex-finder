# codex-finder

A local web app and Python CLI that find Elite Dangerous **Codex** entries you
have *not* yet discovered, ordered by distance from your current system. They
read your local game journal to learn where you are and what you have already
found, then query
the [Spansh](https://spansh.co.uk/bodies) bodies API for the nearest bodies that
hold new entries. Cloud searches also use Canonn Codex reports, the same source
used by SRV Survey's nearest-entry search, to include sites absent from Spansh.

Supported categories:

- `biology` – organic life forms (Codex "Organic Structures")
- `cloud` – Lagrange clouds, storm clouds, Molluscs, pods, trees and crystals
- `anomalies` – Lagrange anomalies

## Requirements

- Python 3.10+
- No third-party packages (standard library only)
- Network access to `spansh.co.uk` and, for cloud searches,
  `us-central1-canonn-api-236217.cloudfunctions.net`

## Web Interface

Start the local server:

```bash
python codex-finder-web.py
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765) in your browser.

- Biology appears on the left, with clouds and anomalies stacked on the right.
  Each category has its own refresh button; searches run only when requested.
- Each category has a search-distance dropdown (500 to 20000 ly), defaulting
  to 500 ly for biology and 10000 ly for clouds and anomalies.
- Results and chosen distances are saved in your browser's `localStorage`.
  Reopening the page restores the last results without another search, and
  results are marked stale after 30 minutes.
- Each result system has a copy-to-clipboard button for the galaxy map.

Cloud searches can take several minutes because they query both Spansh and
Canonn. Saved results are not automatically refreshed after you travel or find
an entry; use the category's refresh button to update them.

To use a different port or journal directory:

```bash
python codex-finder-web.py --port 9000 --journal-dir "/path/to/Elite Dangerous"
```

### Configuring the journal directory

The default path is set in [`codex_finder/config.py`](codex_finder/config.py)
and matches a WSL install. Override it either way:

- environment variable: `CODEX_FINDER_JOURNAL_DIR="/path/to/journal"`
- command-line flag: `--journal-dir "/path/to/journal"`

On native Windows the directory is usually:

```
C:\Users\<name>\Saved Games\Frontier Developments\Elite Dangerous
```

## Command-Line Interface

For terminal use:

```bash
python codex-finder.py biology
python codex-finder.py cloud --nearest 5
python codex-finder.py biology --nearest 5 --within 400ly
python codex-finder.py anomalies --journal-dir "/path/to/Elite Dangerous"
```

`--nearest` sets the maximum number of systems to show (default 10).
`--within` bounds the search radius. When omitted it defaults to 500 ly for
biology and 10000 ly for clouds and anomalies. Both interfaces use the same
search logic and journal configuration.

## How it works

1. **Current system** – the newest journal event carrying a `StarSystem`
   (`FSDJump`, `Location` or `CarrierJump`).
2. **Found entries** – every `CodexEntry` event is scanned across all journal
   files and filtered to the chosen category. Biology is matched at the colour
   variant level (e.g. `Aleoida Arcus - Emerald`): Spansh returns each
   landmark's colour in its `variant` field, so a species you have in one colour
   still counts as new in a colour you are missing.
3. **Spansh query** – the full set of landmark subtypes for the category is
  fetched once (and cached for a week). Cloud and anomaly searches subtract
  already-found subtypes; biology searches query all species and filter found
  colour variants from each body's landmarks. Only new entries are listed.
  Requests are rate-limited to one per second.
4. **Cloud coverage** – when journal coordinates are available, Canonn is
  queried for the nearest systems for each missing cloud subtype. Reports are
  filtered to the requested radius, merged with Spansh results, and sorted
  before the nearest-system limit is applied. This adds one rate-limited
  request per missing subtype. Canonn failures are reported rather than
  silently returning incomplete results.

## Notes and limitations

- Biology is matched per colour variant using each Spansh landmark's `variant`
  field, so it finds the nearest bodies holding colours you have not logged yet.
- Species that come in colours (e.g. `Tubus`) are only reported when Spansh has
  recorded the colour; species with a single Codex entry (e.g. `Tubers`) are
  always reported.
- Cloud and anomaly Codex names map directly to Spansh landmark subtypes; the
  Cloud search also includes Mollusc subtypes from the in-game Cloud hierarchy.
- Canonn cloud reports supply system names, not body names. These entries show
  `body not recorded (Canonn)` unless Spansh supplies a body for the same entry
  in that system. Without journal coordinates, only Spansh is used.
- `--nearest` limits systems across all missing entries, not per species.
  Increasing it may reveal a particular species below the nearest-system cutoff.
- Biology and anomaly searches use Spansh only, so reports missing from its
  database will not appear. Cloud searches supplement Spansh but still depend
  on the coverage of both sources and Spansh's subtype catalogue.
- Journal coordinates allow searches from a current system not catalogued by
  Spansh. If coordinates are unavailable, Spansh must recognise the system name.
