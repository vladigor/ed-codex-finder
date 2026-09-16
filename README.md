# codex-finder

A Python CLI that finds Elite Dangerous **Codex** entries you have *not* yet
discovered, ordered by distance from your current system. It reads your local
game journal to learn where you are and what you have already found, then queries
the [Spansh](https://spansh.co.uk/bodies) bodies API for the nearest bodies that
hold new entries.

Supported categories:

- `biology` – organic life forms (Codex "Organic Structures")
- `cloud` – Lagrange clouds and storm clouds
- `anomalies` – Lagrange anomalies

## Requirements

- Python 3.10+
- No third-party packages (standard library only)
- Network access to `spansh.co.uk`

## Usage

```bash
python codex-finder.py biology
python codex-finder.py cloud --nearest 5
python codex-finder.py biology --nearest 5 --within 400ly
python codex-finder.py anomalies --journal-dir "/path/to/Elite Dangerous"
```

`--within` bounds the search radius (making the query faster). When omitted it
defaults to 500ly for biology and 10000ly for clouds and anomalies.

Example output:

```
Current system: HIP 15304
Category: biology (312 entries already in your journal)

Nearest systems with new biology Codex entries:

 1. Lushertha  (21.31 ly)
      - Stratum Paleas  [Lushertha A 5 a]
      ...
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

## Web UI

A local web app presents all three categories side by side (Biology first):

```bash
python codex-finder-web.py            # then open http://127.0.0.1:8765
python codex-finder-web.py --port 9000 --journal-dir "/path/to/Elite Dangerous"
```

- One column per category, each with its own refresh button (nothing
  auto-refreshes, so it never hits Spansh until you ask it to).
- A per-column search-distance dropdown (500 – 20000 ly), defaulting to 500 ly
  for biology and 10000 ly for clouds and anomalies.
- Results and the chosen distances are saved in your browser's `localStorage`,
  so reopening the page shows your last findings (with a relative "updated"
  time, marked stale after 30 minutes) instead of running a fresh search.
- Each result system has a copy-to-clipboard button for quick pasting into the
  galaxy map.

## How it works

1. **Current system** – the newest journal event carrying a `StarSystem`
   (`FSDJump`, `Location` or `CarrierJump`).
2. **Found entries** – every `CodexEntry` event is scanned across all journal
   files and filtered to the chosen category. Biology is matched at the colour
   variant level (e.g. `Aleoida Arcus - Emerald`): Spansh returns each
   landmark's colour in its `variant` field, so a species you have in one colour
   still counts as new in a colour you are missing.
3. **Spansh query** – the full set of landmark subtypes for the category is
   fetched once (and cached for a week), the already-found entries are
   subtracted, and the remainder is used to search for the nearest bodies. Each
   body's landmarks are compared against your found set to list only the new
   entries. Requests are rate-limited to one per second.

## Proof-of-concept scripts

Built up in stages, as described in `initial_prompt.md`:

- [`poc/poc1_current_system.py`](poc/poc1_current_system.py) – prints the current system.
- [`poc/poc2_codex_unfound.py`](poc/poc2_codex_unfound.py) – lists unfound Cloud entries.

## Notes and limitations

- Biology is matched per colour variant using each Spansh landmark's `variant`
  field, so it finds the nearest bodies holding colours you have not logged yet.
- Species that come in colours (e.g. `Tubus`) are only reported when Spansh has
  recorded the colour; species with a single Codex entry (e.g. `Tubers`) are
  always reported.
- Cloud and anomaly Codex names map directly to Spansh landmark subtypes.
- If your current system is not in Spansh's galaxy database the search cannot
  run; try again from a catalogued system.
