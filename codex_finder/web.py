"""Local web UI for codex-finder.

Serves a single-page app with one column per Codex category (Biology first),
a per-column refresh button (no auto-refresh) and a shared search-distance
dropdown. All data comes from the same journal + Spansh modules the CLI uses.
"""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import config
from .codex import normalise_category
from .finder import find_new_codex_bodies
from .journal import JournalCache
from .spansh import SpanshClient, SpanshError

# Column order for the UI: Biology first, as requested.
UI_CATEGORIES = (
    config.CATEGORY_BIOLOGY,
    config.CATEGORY_CLOUD,
    config.CATEGORY_ANOMALIES,
)
DISTANCE_OPTIONS = (500, 1000, 2000, 5000, 10000, 20000)
DEFAULT_DISTANCE = 1000


class _App:
    """Holds shared state (journal location, a single rate-limited client)."""

    def __init__(self, journal_dir: Path) -> None:
        self.journal = JournalCache(journal_dir)
        self.client = SpanshClient()

    def search(self, category: str, within: float, nearest: int) -> dict:
        cat = normalise_category(category)
        state = self.journal.scan()
        if state.current is None:
            raise RuntimeError("Could not determine your current system from the journal.")
        found = state.found[cat]
        results = find_new_codex_bodies(
            self.client,
            reference_system=state.current.system,
            category=cat,
            found=found,
            top_n=nearest,
            max_distance=within,
        )
        return {
            "category": cat,
            "current_system": state.current.system,
            "within": within,
            "found_count": len(found),
            "results": [
                {
                    "system": r.system,
                    "distance": round(r.distance),
                    "entries": [
                        {"name": name, "body": r.new_entries[name]}
                        for name in sorted(r.new_entries)
                    ],
                }
                for r in results
            ],
        }


def _make_handler(app: _App):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, status: int = 200, content_type: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, obj: dict, status: int = 200) -> None:
            self._send(json.dumps(obj).encode("utf-8"), status)

        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send(INDEX_HTML.encode("utf-8"), content_type="text/html; charset=utf-8")
                return
            if parsed.path == "/api/search":
                self._handle_search(parse_qs(parsed.query))
                return
            self._send_json({"error": "Not found"}, status=404)

        def _handle_search(self, query: dict) -> None:
            category = query.get("category", [""])[0]
            try:
                within = float(query.get("within", [str(DEFAULT_DISTANCE)])[0])
                nearest = int(query.get("nearest", [str(config.TOP_N_SYSTEMS)])[0])
            except ValueError:
                self._send_json({"error": "Invalid within/nearest value."}, status=400)
                return
            try:
                self._send_json(app.search(category, within, nearest))
            except ValueError as exc:  # unknown category
                self._send_json({"error": str(exc)}, status=400)
            except SpanshError as exc:
                self._send_json({"error": f"Spansh query failed: {exc}"}, status=502)
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=409)

        def log_message(self, *args) -> None:  # keep the console quiet
            pass

    return Handler


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ED Codex Finder</title>
<style>
  :root { --bg:#0b0e14; --panel:#141a24; --edge:#26303f; --text:#e6edf3; --muted:#8b98a9; --accent:#ff7f11; --accent2:#4fc3f7; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; background:var(--bg); color:var(--text); }
  header { display:flex; align-items:center; gap:16px; flex-wrap:wrap; padding:14px 20px; border-bottom:1px solid var(--edge); background:var(--panel); position:sticky; top:0; z-index:5; }
  header h1 { font-size:18px; margin:0; color:var(--accent); letter-spacing:.5px; }
  header .spacer { flex:1; }
  label { color:var(--muted); font-size:13px; }
  select, button { font:inherit; color:var(--text); background:#1c2431; border:1px solid var(--edge); border-radius:6px; padding:7px 10px; }
  button { cursor:pointer; }
  button:hover:not(:disabled) { border-color:var(--accent); }
  button:disabled { opacity:.5; cursor:default; }
  .refresh-all { color:var(--accent); border-color:var(--accent); background:transparent; }
  .columns { display:grid; grid-template-columns:repeat(3, 1fr); gap:16px; padding:16px 20px; align-items:start; }
  @media (max-width: 900px) { .columns { grid-template-columns:1fr; } }
  .column { background:var(--panel); border:1px solid var(--edge); border-radius:10px; overflow:hidden; }
  .col-head { display:flex; align-items:center; gap:10px; padding:12px 14px; border-bottom:1px solid var(--edge); }
  .col-head h2 { font-size:15px; margin:0; text-transform:capitalize; }
  .col-head .sys { color:var(--muted); font-size:12px; }
  .col-head .spacer { flex:1; }
  .col-head button { padding:5px 9px; }
  .results { padding:10px 14px 16px; min-height:80px; }
  .muted { color:var(--muted); font-size:13px; }
  .error { color:#ff6b6b; font-size:13px; }
  .system { padding:9px 0; border-bottom:1px dashed var(--edge); }
  .system:last-child { border-bottom:none; }
  .sys-head { display:flex; align-items:baseline; gap:8px; }
  .rank { color:var(--muted); font-variant-numeric:tabular-nums; min-width:1.4em; }
  .sys-head .name { font-weight:600; }
  .sys-head .dist { margin-left:auto; color:var(--accent2); font-variant-numeric:tabular-nums; }
  .results ul { margin:4px 0 0 0; padding-left:26px; }
  .results li { font-size:13px; margin:2px 0; }
  .col-head .dist-sel { padding:4px 7px; font-size:12px; }
  .col-sub { padding:2px 14px 10px; }
  .col-sub .sys { color:var(--muted); font-size:12px; }
  .col-sub .sys.stale { color:var(--accent); }
  .copy-btn { background:transparent; border:none; padding:0 4px; line-height:0; cursor:pointer; color:var(--muted); opacity:.7; }
  .copy-btn:hover { color:var(--text); opacity:1; border:none; }
  .copy-btn.copied { color:#3fb950; opacity:1; }
  .copy-icon { width:12px; height:14px; display:inline-block; vertical-align:middle; }
</style>
</head>
<body>
<header>
  <h1>Elite Dangerous &mdash; Codex Finder</h1>
  <div class="spacer"></div>
  <button class="refresh-all" onclick="refreshAll()">&#8635; Refresh all</button>
</header>
<div class="columns" id="columns"></div>
<script>
const CATEGORIES = ["biology", "cloud", "anomalies"];
const DISTANCES = [500, 1000, 2000, 5000, 10000, 20000];
const DEFAULT_DISTANCES = { biology: 500, cloud: 10000, anomalies: 10000 };
const ESTIMATES = { biology: "about 20-30s", cloud: "about 5s", anomalies: "about 5s" };
const NEAREST = 10;
const STORE_RESULTS = 'codexFinder.results.v1';
const STORE_DISTANCES = 'codexFinder.distances.v1';
const STALE_MS = 30 * 60 * 1000;

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function loadStore() {
  try { return JSON.parse(localStorage.getItem(STORE_RESULTS)) || {}; }
  catch (e) { return {}; }
}
function saveResult(cat, data) {
  const all = loadStore();
  all[cat] = data;
  try { localStorage.setItem(STORE_RESULTS, JSON.stringify(all)); } catch (e) {}
}

function loadDistances() {
  try { return JSON.parse(localStorage.getItem(STORE_DISTANCES)) || {}; }
  catch (e) { return {}; }
}
function distanceFor(cat) {
  const stored = loadDistances()[cat];
  return stored != null ? stored : DEFAULT_DISTANCES[cat];
}
function saveDistance(cat, value) {
  const all = loadDistances();
  all[cat] = Number(value);
  try { localStorage.setItem(STORE_DISTANCES, JSON.stringify(all)); } catch (e) {}
}

function relTime(ts) {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 60) return 'just now';
  const m = Math.round(s / 60); if (m < 60) return m + 'm ago';
  const h = Math.round(m / 60); if (h < 24) return h + 'h ago';
  return Math.round(h / 24) + 'd ago';
}

function buildUI() {
  document.getElementById('columns').innerHTML = CATEGORIES.map(cat => {
    const chosen = distanceFor(cat);
    const opts = DISTANCES.map(d => `<option value="${d}" ${String(d)===String(chosen)?'selected':''}>${d.toLocaleString()} ly</option>`).join('');
    return `
    <section class="column" data-col="${cat}">
      <div class="col-head">
        <h2>${cat}</h2>
        <span class="spacer"></span>
        <select class="dist-sel" title="Search distance" onchange="saveDistance('${cat}', this.value)">${opts}</select>
        <button onclick="refresh('${cat}')" title="Refresh">&#8635;</button>
      </div>
      <div class="col-sub"><span class="sys"></span></div>
      <div class="results"><p class="muted">Press &#8635; to search.</p></div>
    </section>`;
  }).join('');
  document.addEventListener('click', onCopyClick);
  restore();
}

function onCopyClick(ev) {
  const btn = ev.target.closest('.copy-btn');
  if (!btn) return;
  const name = btn.getAttribute('data-copy');
  navigator.clipboard.writeText(name).then(() => {
    btn.classList.add('copied');
    setTimeout(() => { btn.classList.remove('copied'); }, 1000);
  }).catch(() => {});
}

function restore() {
  const all = loadStore();
  CATEGORIES.forEach(cat => { if (all[cat]) render(cat, all[cat]); });
}

async function refresh(cat) {
  const col = document.querySelector(`[data-col="${cat}"]`);
  const body = col.querySelector('.results');
  const btn = col.querySelector('.col-head button');
  const within = col.querySelector('.dist-sel').value;
  body.innerHTML = `<p class="muted">Please be patient &mdash; the ${cat} search typically takes ${ESTIMATES[cat]}&hellip;</p>`;
  btn.disabled = true;
  try {
    const resp = await fetch(`/api/search?category=${cat}&within=${within}&nearest=${NEAREST}`);
    const data = await resp.json();
    if (!resp.ok) { body.innerHTML = `<p class="error">${esc(data.error || 'Error')}</p>`; return; }
    data.savedAt = Date.now();
    saveResult(cat, data);
    render(cat, data);
  } catch (e) {
    body.innerHTML = `<p class="error">${esc(e)}</p>`;
  } finally {
    btn.disabled = false;
  }
}

function render(cat, data) {
  const col = document.querySelector(`[data-col="${cat}"]`);
  const sysEl = col.querySelector('.sys');
  const stale = data.savedAt && (Date.now() - data.savedAt > STALE_MS);
  sysEl.classList.toggle('stale', !!stale);
  const when = data.savedAt
    ? ` \u00b7 updated ${relTime(data.savedAt)}${stale ? ' ⚠️' : ''}`
    : '';
  sysEl.textContent = `${data.current_system} \u00b7 ${data.found_count.toLocaleString()} logged${when}`;
  const body = col.querySelector('.results');
  if (!data.results.length) {
    body.innerHTML = `<p class="muted">No new entries within ${Number(data.within).toLocaleString()} ly.</p>`;
    return;
  }
  body.innerHTML = data.results.map((s, i) => `
    <div class="system">
      <div class="sys-head">
        <span class="rank">${i + 1}</span>
        <span class="name">${esc(s.system)}</span>
        <button class="copy-btn" data-copy="${esc(s.system)}" title="Copy system name" aria-label="Copy system name"><svg class="copy-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><path fill="currentColor" d="M384 336H192c-8.8 0-16-7.2-16-16V64c0-8.8 7.2-16 16-16l140.1 0L400 115.9V320c0 8.8-7.2 16-16 16zM192 384H384c35.3 0 64-28.7 64-64V115.9c0-12.7-5.1-24.9-14.1-33.9L366.1 14.1c-9-9-21.2-14.1-33.9-14.1H192c-35.3 0-64 28.7-64 64V320c0 35.3 28.7 64 64 64zM64 128c-35.3 0-64 28.7-64 64V448c0 35.3 28.7 64 64 64H256c35.3 0 64-28.7 64-64V416H272v32c0 8.8-7.2 16-16 16H64c-8.8 0-16-7.2-16-16V192c0-8.8 7.2-16 16-16H96V128H64z"></path></svg></button>
        <span class="dist">${s.distance.toLocaleString()} ly</span>
      </div>
      <ul>${s.entries.map(e => `<li>${esc(e.name)} <span class="muted">[${esc(e.body)}]</span></li>`).join('')}</ul>
    </div>`).join('');
}

function refreshAll() { CATEGORIES.forEach(refresh); }

buildUI();
</script>
</body>
</html>
"""


def _prewarm(app: _App) -> None:
    try:
        app.journal.scan()
    except OSError:
        pass


def serve(host: str = "127.0.0.1", port: int = 8765, journal_dir: Path | None = None) -> int:
    journal_dir = journal_dir or config.get_journal_dir()
    if not journal_dir.is_dir():
        print(f"Journal directory not found: {journal_dir}")
        return 2
    app = _App(journal_dir)
    # Parse the journal history in the background so the first refresh is fast.
    threading.Thread(target=_prewarm, args=(app,), daemon=True).start()
    httpd = ThreadingHTTPServer((host, port), _make_handler(app))
    print(f"codex-finder web UI running at http://{host}:{port}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="codex-finder-web",
        description="Run the codex-finder local web UI.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8765, help="Port (default 8765).")
    parser.add_argument("--journal-dir", type=Path, default=None, help="Override the journal directory.")
    args = parser.parse_args(argv)
    return serve(host=args.host, port=args.port, journal_dir=args.journal_dir)


if __name__ == "__main__":
    raise SystemExit(main())
