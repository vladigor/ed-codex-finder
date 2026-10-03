"""Read nearby Codex reports from the Canonn endpoint used by SRV Survey."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config


_NEAREST_URL = (
    "https://us-central1-canonn-api-236217.cloudfunctions.net/query/nearest/codex"
)


class CanonnError(RuntimeError):
    """Raised when Canonn Codex reports cannot be retrieved."""


class CanonnClient:
    def __init__(self, *, min_interval: float = 1.1) -> None:
        self._min_interval = min_interval
        self._last_request_at = 0.0
        self._lock = threading.Lock()

    def nearest_codex(
        self,
        *,
        reference_coords: tuple[float, float, float],
        name: str,
        limit: int,
    ) -> list[dict]:
        """Return nearby reports; the API supplies systems, not body names."""
        coord_x, coord_y, coord_z = reference_coords
        params = urllib.parse.urlencode(
            {"x": coord_x, "y": coord_y, "z": coord_z, "name": name, "limit": limit}
        )
        request = urllib.request.Request(
            f"{_NEAREST_URL}?{params}", headers={"User-Agent": config.USER_AGENT}
        )
        with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    result = json.load(response)
            except (urllib.error.URLError, OSError, ValueError) as exc:
                raise CanonnError(f"Canonn query failed for {name!r}: {exc}") from exc
            finally:
                self._last_request_at = time.monotonic()
        if not isinstance(result, dict) or not isinstance(result.get("nearest"), list):
            raise CanonnError(f"Canonn returned an invalid response for {name!r}")
        return result["nearest"]