"""
Chartmetric API client — primary data stream.

Handles token refresh, rate limiting with backoff, raw response archiving,
and all endpoints used by the ingestion + ML pipeline.

Config (.env):
    CHARTMETRIC_REFRESH_TOKEN=...

Usage:
    python -m ingestion.chartmetric_client --search "Chris Stussy"
"""

import gzip
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import click
import httpx

from config import CHARTMETRIC_REFRESH_TOKEN

_BASE = "https://api.chartmetric.com/api"
_RAW_DIR = Path(__file__).parent / "raw" / "chartmetric"
_RAW_DIR.mkdir(parents=True, exist_ok=True)

log = logging.getLogger(__name__)

# Standard tier: ~30 req/min. We aim for ~20 to leave headroom.
_MIN_INTERVAL = 3.0   # seconds between requests


class ChartmetricClient:
    def __init__(self):
        self._token: Optional[str] = None
        self._token_expires: datetime = datetime.utcnow()
        self._last_request: float = 0.0

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _refresh_token(self):
        if not CHARTMETRIC_REFRESH_TOKEN:
            raise RuntimeError("CHARTMETRIC_REFRESH_TOKEN not set in .env")
        resp = httpx.post(
            f"{_BASE}/token",
            json={"refreshtoken": CHARTMETRIC_REFRESH_TOKEN},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires = datetime.utcnow() + timedelta(seconds=expires_in - 120)
        log.debug("CM token refreshed, expires in %ds", expires_in)

    def _get_token(self) -> str:
        if not self._token or datetime.utcnow() >= self._token_expires:
            self._refresh_token()
        return self._token

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _throttle(self):
        elapsed = time.monotonic() - self._last_request
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        self._last_request = time.monotonic()

    def _get(self, path: str, params: Optional[dict] = None, archive: bool = True) -> dict:
        """GET with throttle, retry on 429/5xx, and raw archiving."""
        self._throttle()

        for attempt in range(4):
            try:
                resp = httpx.get(
                    f"{_BASE}{path}",
                    headers={"Authorization": f"Bearer {self._get_token()}"},
                    params={k: v for k, v in (params or {}).items() if v is not None},
                    timeout=20,
                )
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", "60"))
                    log.warning("Rate limited — sleeping %ds", wait)
                    time.sleep(wait)
                    continue
                if resp.status_code == 401:
                    self._refresh_token()
                    continue
                resp.raise_for_status()
                data = resp.json()

                if archive:
                    slug = path.replace("/", "_").strip("_")
                    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
                    dest = _RAW_DIR / f"{slug}_{ts}.json.gz"
                    with gzip.open(dest, "wt", encoding="utf-8") as f:
                        json.dump({"path": path, "params": params, "body": data}, f)

                return data

            except httpx.HTTPStatusError as exc:
                if attempt < 3 and exc.response.status_code >= 500:
                    time.sleep(2 ** attempt)
                    continue
                raise

        raise RuntimeError(f"CM request failed after retries: {path}")

    # ------------------------------------------------------------------
    # Artist discovery
    # ------------------------------------------------------------------

    def search_artist(self, name: str, limit: int = 5) -> list[dict]:
        """Search by name. Returns list of Chartmetric artist objects."""
        data = self._get("/artist/search", {"q": name, "limit": limit}, archive=False)
        return data.get("obj", {}).get("artists", [])

    def get_artist_metadata(self, cm_id: int) -> dict:
        """Full artist record including genres, labels, image, social links."""
        data = self._get(f"/artist/{cm_id}")
        return data.get("obj", {})

    def get_similar_artists(self, cm_id: int, limit: int = 20) -> list[dict]:
        """Artists considered similar by Chartmetric's model."""
        data = self._get(f"/artist/{cm_id}/similar/artists", {"limit": limit})
        return data.get("obj", {}).get("artists", [])

    # ------------------------------------------------------------------
    # Time-series: Spotify
    # ------------------------------------------------------------------

    def get_spotify_stats(self, cm_id: int, since: str = "2020-01-01") -> list[dict]:
        """
        Daily Spotify: monthly listeners, followers, popularity.
        Returns [{date, listeners, followers, popularity}, ...]
        """
        until = datetime.utcnow().strftime("%Y-%m-%d")
        data = self._get(f"/artist/{cm_id}/stat/spotify", {"since": since, "until": until})
        return data.get("obj", [])

    def get_spotify_playlists(self, cm_id: int, status: str = "current") -> list[dict]:
        """Current Spotify playlist placements with follower counts."""
        data = self._get(
            f"/artist/{cm_id}/playlists/spotify",
            {"status": status, "limit": 200},
        )
        return data.get("obj", {}).get("playlists", [])

    # ------------------------------------------------------------------
    # Time-series: Social
    # ------------------------------------------------------------------

    def get_social_stats(self, cm_id: int, platform: str, since: str = "2020-01-01") -> list[dict]:
        """
        platform: 'instagram' | 'tiktok' | 'youtube' | 'soundcloud'
        Returns [{date, followers/fans/subscribers, ...}, ...]
        """
        until = datetime.utcnow().strftime("%Y-%m-%d")
        data = self._get(f"/artist/{cm_id}/stat/{platform}", {"since": since, "until": until})
        return data.get("obj", [])

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------

    def get_beatport_charts(self, cm_id: int) -> list[dict]:
        """Beatport chart entries — rank + chart date."""
        data = self._get(f"/artist/{cm_id}/stat/beatport")
        return data.get("obj", [])

    # ------------------------------------------------------------------
    # Geo
    # ------------------------------------------------------------------

    def get_geo_listeners(self, cm_id: int) -> dict:
        """
        Current listener distribution by city and country.
        Returns {"cities": [...], "countries": [...]}
        """
        data = self._get(f"/artist/{cm_id}/where-people-listen", {"latest": True})
        return data.get("obj", {})


# ------------------------------------------------------------------
# CLI smoke-test
# ------------------------------------------------------------------

@click.command()
@click.option("--search", "query", default=None, help="Artist name to search")
@click.option("--artist-id", "cm_id", default=None, type=int, help="CM artist ID to inspect")
def main(query: Optional[str], cm_id: Optional[int]):
    logging.basicConfig(level=logging.INFO)
    client = ChartmetricClient()

    if query:
        results = client.search_artist(query)
        print(f"Search '{query}': {len(results)} results")
        for r in results:
            print(f"  [{r.get('id')}] {r.get('name')} — {r.get('sp_monthly_listeners', '?')} listeners")

    if cm_id:
        meta = client.get_artist_metadata(cm_id)
        print(f"\nArtist: {meta.get('name')}")
        print(f"  Genres: {meta.get('genres', [])}")
        stats = client.get_spotify_stats(cm_id)
        if stats:
            latest = stats[-1]
            print(f"  Spotify ({latest.get('date')}): {latest.get('listeners', '?')} listeners")


if __name__ == "__main__":
    main()
