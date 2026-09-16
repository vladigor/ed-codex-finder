"""A small, rate-limited client for the Spansh bodies API.

Only the two endpoints we need are implemented:

* ``field_values/landmark_subtype`` - the full list of landmark subtypes, used to
  build the universe of Codex entries per category.
* ``bodies/search`` - the synchronous body search, filtered by landmark subtype
  and sorted by distance from a reference system.

All requests go through :meth:`SpanshClient._request`, which enforces the
one-request-per-second courtesy limit from ``spansh_api.md``.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import threading
from pathlib import Path

from . import config


class SpanshError(RuntimeError):
    """Raised when the Spansh API returns an error or cannot be reached."""


class SpanshClient:
    def __init__(
        self,
        *,
        min_interval: float = config.SPANSH_MIN_REQUEST_INTERVAL,
        cache_dir: Path = config.CACHE_DIR,
    ) -> None:
        self._min_interval = min_interval
        self._cache_dir = cache_dir
        self._last_request_at = 0.0
        # Serialises requests so the rate limit holds across web UI threads.
        self._lock = threading.Lock()

    # -- low level ----------------------------------------------------------
    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = self._min_interval - elapsed
        if wait > 0:
            time.sleep(wait)

    def _request(self, url: str, *, payload: dict | None = None) -> dict:
        # Guard against ever calling a host other than Spansh. All URLs are
        # built from constants in config, but this makes the boundary explicit.
        if not url.startswith(config.SPANSH_BASE_URL + "/"):
            raise SpanshError(f"Refusing to call non-Spansh URL: {url}")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"User-Agent": config.USER_AGENT}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers)
        with self._lock:
            self._throttle()
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    body = response.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                raise SpanshError(f"Spansh HTTP {exc.code} for {url}") from exc
            except urllib.error.URLError as exc:
                raise SpanshError(f"Could not reach Spansh: {exc.reason}") from exc
            finally:
                self._last_request_at = time.monotonic()

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise SpanshError("Spansh returned invalid JSON") from exc
        if isinstance(parsed, dict) and parsed.get("error"):
            raise SpanshError(f"Spansh error: {parsed['error']}")
        return parsed

    # -- endpoints ----------------------------------------------------------
    def landmark_subtypes(self) -> list[str]:
        """All landmark subtype names, cached locally for a week."""
        cached = self._read_cache("landmark_subtype.json")
        if cached is not None:
            return cached
        result = self._request(
            f"{config.SPANSH_FIELD_VALUES_URL}/landmark_subtype"
        )
        values = sorted(result.get("min_max", {}).keys())
        self._write_cache("landmark_subtype.json", values)
        return values

    def search_bodies(
        self,
        *,
        reference_system: str,
        landmark_subtypes: list[str],
        max_distance: float | None = None,
        size: int = 50,
        page: int = 0,
    ) -> dict:
        """Search for bodies near ``reference_system`` with the given subtypes.

        ``max_distance`` (light years), when given, caps the search radius, which
        greatly reduces the number of results the server returns.
        """
        filters: dict = {"landmark_subtype": {"value": landmark_subtypes}}
        if max_distance is not None:
            filters["distance"] = {"min": "0", "max": str(max_distance)}
        payload = {
            "reference_system": reference_system,
            "filters": filters,
            "sort": [{"distance": {"direction": "asc"}}],
            "size": size,
            "page": page,
        }
        return self._request(config.SPANSH_SEARCH_URL, payload=payload)

    # -- cache --------------------------------------------------------------
    def _read_cache(self, name: str) -> list[str] | None:
        path = self._cache_dir / name
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            return None
        if age > config.CACHE_TTL_SECONDS:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(self, name: str, values: list[str]) -> None:
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            (self._cache_dir / name).write_text(
                json.dumps(values), encoding="utf-8"
            )
        except OSError:
            # Caching is best-effort; a failure here must not break the run.
            pass
