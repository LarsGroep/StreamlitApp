"""
Beatport Genre Charts Spider (v2).

Scrapes the top-100 chart for each configured genre from Beatport's Next.js pages.
Data is embedded in <script id="__NEXT_DATA__"> — no Playwright required.

Input:  input/genres.json  (list of {name, slug, id, framework})
Output: BeatportChartItem.jsonl

Usage:
    cd scraper && scrapy crawl beatport_charts
    cd scraper && scrapy crawl beatport_charts -a genres_file=../input/genres.json
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

import scrapy

from scraper.items import BeatportChartItem

log = logging.getLogger(__name__)

_BASE = "https://www.beatport.com"
_INPUT = Path(__file__).parent.parent.parent / "input" / "genres.json"


def _load_genres(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _item_id(genre_id: int, track_id: int) -> str:
    raw = f"bp_chart|{genre_id}|{track_id}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _extract_tracks(next_data: dict) -> list[dict]:
    """Navigate __NEXT_DATA__ to find the chart track list.

    Beatport embeds React Query dehydrated state. The tracks array sits under
    the first query whose data has a 'results' list with track-shaped objects.
    Falls back to props.pageProps.tracks if that path exists.
    """
    props = next_data.get("props", {})
    page_props = props.get("pageProps", {})

    # Fast path: direct pageProps.tracks
    if isinstance(page_props.get("tracks"), list):
        return page_props["tracks"]

    # React Query dehydrated state
    dehydrated = page_props.get("dehydratedState", {})
    for query in dehydrated.get("queries", []):
        state_data = (query.get("state") or {}).get("data") or {}
        results = state_data.get("results")
        if isinstance(results, list) and results and isinstance(results[0], dict):
            if "artists" in results[0] or "label" in results[0]:
                return results

    return []


class BeatportChartsSpider(scrapy.Spider):
    name = "beatport_charts"

    custom_settings = {
        "DOWNLOAD_DELAY": 4.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 0.5,
        # Beatport uses Cloudflare — need real browser rendering
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 45000,
    }

    def __init__(self, genres_file=None, **kwargs):
        super().__init__(**kwargs)
        path = Path(genres_file) if genres_file else _INPUT
        self._genres = _load_genres(path)
        log.info("Loaded %d genres from %s", len(self._genres), path)

    async def start(self):
        for genre in self._genres:
            url = f"{_BASE}/genre/{genre['slug']}/{genre['id']}/top-100"
            yield scrapy.Request(
                url,
                callback=self.parse_chart,
                meta={
                    "genre": genre,
                    "playwright": True,
                    "playwright_include_page": False,
                },
            )

    def parse_chart(self, response):
        genre = response.meta["genre"]

        raw = response.css("script#__NEXT_DATA__::text").get()
        if not raw:
            log.warning("No __NEXT_DATA__ found for genre '%s' at %s", genre["name"], response.url)
            return

        try:
            next_data = json.loads(raw)
        except json.JSONDecodeError as exc:
            log.error("JSON parse error for '%s': %s", genre["name"], exc)
            return

        tracks = _extract_tracks(next_data)
        if not tracks:
            log.warning(
                "No tracks extracted for '%s' — Beatport page structure may have changed. "
                "Check __NEXT_DATA__ keys: %s",
                genre["name"],
                list((next_data.get("props") or {}).get("pageProps") or {}),
            )
            return

        log.info("Genre '%s': %d tracks", genre["name"], len(tracks))
        scraped_at = datetime.utcnow().isoformat()

        for rank, track in enumerate(tracks, start=1):
            track_id = track.get("id")
            if not track_id:
                continue

            artists = [a["name"] for a in (track.get("artists") or []) if a.get("name")]
            label_obj = track.get("label") or {}

            yield BeatportChartItem(
                id=_item_id(genre["id"], track_id),
                rank=rank,
                genre=genre["name"],
                genre_id=genre["id"],
                title=track.get("name"),
                mix_name=track.get("mix_name"),
                artists=artists,
                label=label_obj.get("name"),
                label_id=label_obj.get("id"),
                publish_date=track.get("publish_date") or track.get("new_release_date"),
                scraped_at=scraped_at,
            )
