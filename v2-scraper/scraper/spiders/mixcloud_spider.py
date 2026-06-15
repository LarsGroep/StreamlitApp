"""
Mixcloud Show Spider (v2).

Uses the Mixcloud public JSON API to fetch episode lists from
framework-relevant shows: Circoloco Radio, Solid Grooves Radio,
Boiler Room, BBC Radio 1, Drumcode Live, Afterlife Podcast, etc.

Input:  input/mixcloud_shows.json  (list of {username, show_name, framework})
Output: MixcloudEpisodeItem.jsonl

No Playwright needed — Mixcloud has a clean public REST API.

Usage:
    cd scraper && scrapy crawl mixcloud_shows
    cd scraper && scrapy crawl mixcloud_shows -a shows_file=../input/mixcloud_shows.json
"""

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import scrapy

from scraper.items import MixcloudEpisodeItem

log = logging.getLogger(__name__)

_API = "https://api.mixcloud.com"
_PER_PAGE = 100
_MAX_PAGES = 10          # up to 1000 episodes per show
_INPUT = Path(__file__).parent.parent.parent / "input" / "mixcloud_shows.json"

# Patterns to extract featured artist names from episode titles.
# "Solid Grooves Radio 278 feat. Marco Carola"
# "Circoloco Radio 095 w/ Chris Stussy"
# "DC10 Ibiza — Josh Baker B2B Rossi."
_FEAT_PATTERNS = [
    re.compile(r"\bfeat\.?\s+(.+)$", re.IGNORECASE),
    re.compile(r"\bft\.?\s+(.+)$", re.IGNORECASE),
    re.compile(r"\bw/\s+(.+)$", re.IGNORECASE),
    re.compile(r"\bwith\s+(.+)$", re.IGNORECASE),
    re.compile(r"[-–—]\s*(.+)$"),          # "Show Name — Artist" suffix
    re.compile(r":\s*(.+)$"),              # "Show Name: Artist"
]
# B2B / B3B splits
_B2B = re.compile(r"\s+b[23]b\s+", re.IGNORECASE)
# Trailing date patterns added by NTS/DJ Mag: " - 12th June 2026" or " - 2026-06-12"
_TRAILING_DATE = re.compile(
    r"\s*[-–—]\s*(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2})\s*$",
    re.IGNORECASE,
)
# Trailing "N Min/Hour Radio Mix" junk from compilation titles
_TRAILING_MIX_JUNK = re.compile(r"\s+\d+\s+min\b.*$", re.IGNORECASE)
# Collaborator splitter: " & " or " x " (must be surrounded by spaces to avoid splitting "Mix")
_COLLAB_SPLIT = re.compile(r"\s+&\s+|\s+x\s+", re.IGNORECASE)


def _load_shows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _extract_artists(title: str) -> list[str]:
    """Best-effort extraction of featured artist names from an episode title."""
    for pattern in _FEAT_PATTERNS:
        m = pattern.search(title)
        if m:
            raw = m.group(1).strip()
            # Strip trailing broadcast date (e.g. "Artist - 12th June 2026")
            raw = _TRAILING_DATE.sub("", raw).strip()
            raw = _TRAILING_MIX_JUNK.sub("", raw).strip()
            # Split B2B
            parts = _B2B.split(raw)
            # Also split by " & " or " x " (spaces required to avoid splitting words like "Mix")
            result = []
            for part in parts:
                for subpart in _COLLAB_SPLIT.split(part):
                    name = subpart.strip().rstrip(".,)")
                    if name and len(name) > 1:
                        result.append(name)
            return result
    return []


def _item_id(key: str) -> str:
    return hashlib.md5(key.encode()).hexdigest()[:16]


class MixcloudShowsSpider(scrapy.Spider):
    name = "mixcloud_shows"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        # Override default headers — Mixcloud API returns JSON
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "User-Agent": "lofi-research-bot/2.0",
        },
    }

    def __init__(self, shows_file=None, **kwargs):
        super().__init__(**kwargs)
        path = Path(shows_file) if shows_file else _INPUT
        self._shows = _load_shows(path)
        log.info("Loaded %d shows from %s", len(self._shows), path)

    async def start(self):
        for show in self._shows:
            url = f"{_API}/{show['username']}/cloudcasts/?limit={_PER_PAGE}"
            yield scrapy.Request(
                url,
                callback=self.parse_page,
                meta={"show": show, "page": 1, "playwright": False},
            )

    def parse_page(self, response):
        show = response.meta["show"]
        page = response.meta["page"]

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as exc:
            log.error("JSON error for show '%s' page %d: %s", show["username"], page, exc)
            return

        episodes = data.get("data") or []
        log.info("Show '%s' page %d: %d episodes", show["username"], page, len(episodes))

        scraped_at = datetime.utcnow().isoformat()
        for ep in episodes:
            key = ep.get("key", "")
            name = ep.get("name", "")
            tags = [t.get("name") for t in (ep.get("tags") or []) if t.get("name")]
            artists = [] if show.get("skip_artist_extraction") else _extract_artists(name)

            yield MixcloudEpisodeItem(
                id=_item_id(key),
                show_username=show["username"],
                show_name=show.get("show_name", show["username"]),
                framework=show.get("framework", "unknown"),
                episode_name=name,
                url=ep.get("url"),
                created_time=ep.get("created_time"),
                play_count=ep.get("play_count"),
                listener_count=ep.get("listener_count"),
                favorite_count=ep.get("favorite_count"),
                featured_artists=artists,
                tags=tags,
                scraped_at=scraped_at,
            )

        # Follow pagination
        next_url = (data.get("paging") or {}).get("next")
        if next_url and page < _MAX_PAGES:
            yield scrapy.Request(
                next_url,
                callback=self.parse_page,
                meta={"show": show, "page": page + 1},
            )
        elif page >= _MAX_PAGES:
            log.info("Show '%s': reached max pages (%d)", show["username"], _MAX_PAGES)
