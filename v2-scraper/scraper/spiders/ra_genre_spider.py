"""
RA Genre Artists Spider (v2).

Uses the RA GraphQL eventListings API to find artists from recent events by genre.
Fetches the most recent 500 events per genre (last 10 pages of sorted-asc results).
Aggregates artist appearance counts and venue/city lists.

Confirmed working RA genre strings:
  techhouse, house, deephouse, techno, afrohouse, trance, garage,
  industrial, progressivehouse, downtempo

Input:  input/ra_genre_tags.json  (list of {ra_genre, framework, label})
Output: RAGenreArtistItem.jsonl

Usage:
    cd scraper && scrapy crawl ra_genre_artists
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

import scrapy

from scraper.items import RAGenreArtistItem

log = logging.getLogger(__name__)

_GRAPHQL = "https://ra.co/graphql"
_INPUT = Path(__file__).parent.parent.parent / "input" / "ra_genre_tags.json"

_DATE_FROM = "2025-01-01"
_DATE_TO = datetime.utcnow().strftime("%Y-%m-%d")
_PAGE_SIZE = 50
_TOTAL_CAP = 10_000
_PAGES_TO_SCRAPE = 10  # last 10 pages = 500 most recent events per genre

# Dates are inlined (not variables) because RA's listingDate expects DateTime type,
# not String! — parameterized variables fail with type mismatch.
_QUERY_TEMPLATE = """
query GET_EVENTS_BY_GENRE($genre: String!, $page: Int!) {{
  eventListings(
    filters: {{ genre: {{eq: $genre}}, listingDate: {{gte: "{date_from}", lte: "{date_to}"}} }}
    pageSize: 50
    page: $page
  ) {{
    data {{
      event {{
        id
        date
        artists {{ name }}
        venue {{
          name
          area {{ name }}
        }}
      }}
    }}
    totalResults
  }}
}}
"""


def _load_tags(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _item_id(ra_genre: str, artist_name: str) -> str:
    raw = f"ra_genre|{ra_genre}|{artist_name.lower()}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _json_from(response) -> dict:
    if hasattr(response, "json"):
        try:
            return response.json()
        except Exception:
            pass
    try:
        pre = response.css("pre ::text").get()
        if pre:
            return json.loads(pre)
    except Exception:
        pass
    return json.loads(response.text)


def _accumulate(events: list, aggregated: dict) -> None:
    for ev_wrap in events:
        event = ev_wrap.get("event") or {}
        venue_obj = event.get("venue") or {}
        area_obj = venue_obj.get("area") or {}
        venue = venue_obj.get("name")
        city = area_obj.get("name")
        for artist in event.get("artists") or []:
            name = artist.get("name")
            if not name:
                continue
            if name not in aggregated:
                aggregated[name] = {"count": 0, "venues": set(), "cities": set()}
            aggregated[name]["count"] += 1
            if venue:
                aggregated[name]["venues"].add(venue)
            if city:
                aggregated[name]["cities"].add(city)


class RAGenreArtistsSpider(scrapy.Spider):
    name = "ra_genre_artists"
    allowed_domains = ["ra.co"]

    def __init__(self, tags_file=None, **kwargs):
        super().__init__(**kwargs)
        path = Path(tags_file) if tags_file else _INPUT
        self._tags = _load_tags(path)
        log.info("Loaded %d RA genre tags from %s", len(self._tags), path)

    async def start(self):
        for tag_cfg in self._tags:
            yield self._build_request(tag_cfg, page=1, meta_extra={"probe": True})

    def _build_request(self, tag_cfg: dict, page: int, meta_extra: dict | None = None):
        query = _QUERY_TEMPLATE.format(date_from=_DATE_FROM, date_to=_DATE_TO)
        body = json.dumps({
            "query": query,
            "variables": {
                "genre": tag_cfg["ra_genre"],
                "page": page,
            },
        }).encode()
        meta = {
            "tag_cfg": tag_cfg,
            "page": page,
            "playwright": False,
        }
        if meta_extra:
            meta.update(meta_extra)
        return scrapy.Request(
            _GRAPHQL,
            method="POST",
            body=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://ra.co",
                "Referer": "https://ra.co/events",
            },
            callback=self.parse_probe if meta.get("probe") else self.parse_page,
            meta=meta,
        )

    def parse_probe(self, response):
        """Page 1 probe: learn total, queue the last _PAGES_TO_SCRAPE pages."""
        tag_cfg = response.meta["tag_cfg"]

        try:
            data = _json_from(response)
        except Exception as exc:
            log.error("JSON error probing '%s': %s", tag_cfg["ra_genre"], exc)
            return

        listings = (data.get("data") or {}).get("eventListings") or {}
        total = listings.get("totalResults") or 0
        log.info("Genre '%s': %d total events", tag_cfg["ra_genre"], total)

        if total == 0:
            return

        last_page = min(_TOTAL_CAP // _PAGE_SIZE, max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE))
        start_page = max(1, last_page - _PAGES_TO_SCRAPE + 1)
        pages = list(range(start_page, last_page + 1))

        # Shared state across all page callbacks for this genre
        state = {
            "aggregated": {},
            "remaining": len(pages),  # decremented per page; emit when 0
        }

        # Page 1 data already in hand — process it if it's in our target range
        if 1 in pages:
            _accumulate(listings.get("data") or [], state["aggregated"])
            state["remaining"] -= 1
            pages.remove(1)

        if state["remaining"] == 0:
            yield from self._emit(tag_cfg, state["aggregated"])
            return

        for page in pages:
            yield self._build_request(tag_cfg, page=page, meta_extra={"state": state})

    def parse_page(self, response):
        tag_cfg = response.meta["tag_cfg"]
        page = response.meta["page"]
        state: dict = response.meta["state"]

        try:
            data = _json_from(response)
        except Exception as exc:
            log.error("JSON error page %d '%s': %s", page, tag_cfg["ra_genre"], exc)
        else:
            listings = (data.get("data") or {}).get("eventListings") or {}
            events = listings.get("data") or []
            log.debug("Genre '%s' page %d: %d events", tag_cfg["ra_genre"], page, len(events))
            _accumulate(events, state["aggregated"])

        state["remaining"] -= 1
        if state["remaining"] == 0:
            yield from self._emit(tag_cfg, state["aggregated"])

    def _emit(self, tag_cfg: dict, aggregated: dict):
        scraped_at = datetime.utcnow().isoformat()
        ra_genre = tag_cfg["ra_genre"]
        for artist_name, d in aggregated.items():
            yield RAGenreArtistItem(
                id=_item_id(ra_genre, artist_name),
                genre_tag=ra_genre,
                artist_name=artist_name,
                ra_slug=None,
                event_count=d["count"],
                venues=sorted(d["venues"]),
                cities=sorted(d["cities"]),
                scraped_at=scraped_at,
            )
        log.info("Genre '%s': emitted %d artists", ra_genre, len(aggregated))
