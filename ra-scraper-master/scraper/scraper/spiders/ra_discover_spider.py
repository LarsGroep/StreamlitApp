"""
Recursive co-artist discovery spider.

Starts from seed artists in artists.txt, scrapes their past + upcoming events,
extracts every co-artist from lineups, and queues those artists too.
Depth 0 = seeds, depth 1 = co-artists of seeds, depth 2 = co-artists of those, etc.

Settings (pass via -s KEY=VALUE):
  MAX_DEPTH    how many hops from seed to follow  (default: 1)
  MAX_ARTISTS  hard cap on total artists queued   (default: 500)
  EVENT_LIMIT  events fetched per artist          (default: 50)
"""

import json
import re
import unicodedata
import scrapy

from scraper.items import EventItem, EventLineupItem
from scraper.utils.file_io import get_artists
from scraper.utils.logger import get_logger

log = get_logger(__name__)

_GRAPHQL_URL = "https://ra.co/graphql"

# EventQueryType! is non-nullable — must be hardcoded, not passed as a variable.
# Artist.slug is not available on nested artist objects — only name is.
_QUERY_LATEST = """
query GET_ARTIST_EVENTS_LATEST($slug: String!, $limit: Int) {
  artist(slug: $slug) {
    id
    name
    events(limit: $limit, type: LATEST) {
      id
      date
      title
      venue {
        name
        area { name }
      }
      artists { name }
    }
  }
}
"""


# PAST enum value does not exist in RA's schema — run ra_probe to find alternatives.
# Only LATEST is confirmed working.
_QUERIES = {"LATEST": _QUERY_LATEST}


def _json_from_response(response):
    pre = response.css("pre ::text").get()
    if pre:
        return json.loads(pre)
    return json.loads(response.text)


def _name_to_slug(name):
    """Best-effort conversion of an artist display name to an RA URL slug."""
    normalized = unicodedata.normalize("NFD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = ascii_name.lower().strip()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


class RaDiscoverSpider(scrapy.Spider):
    name = "ra_discover_spider"
    allowed_domains = ["ra.co"]
    start_urls = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._queued = set()

    def _settings_int(self, key, default):
        val = getattr(self, key, None)
        if val is not None:
            return int(val)
        return self.crawler.settings.getint(key, default)

    async def start(self):
        max_artists = self._settings_int("MAX_ARTISTS", 500)
        event_limit = self._settings_int("EVENT_LIMIT", 50)

        seeds = get_artists("artists.txt")
        log.info("Starting discovery from %d seed artists", len(seeds))

        for slug in seeds:
            if slug in self._queued:
                continue
            self._queued.add(slug)
            for req in self._artist_requests(slug, depth=0, event_limit=event_limit, max_artists=max_artists):
                yield req

    def _artist_requests(self, slug, depth, event_limit, max_artists):
        for event_type, query in _QUERIES.items():
            body = json.dumps({
                "query": query,
                "variables": {"slug": slug, "limit": event_limit},
            }).encode()
            yield scrapy.Request(
                _GRAPHQL_URL,
                method="POST",
                body=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Origin": "https://ra.co",
                    "Referer": f"https://ra.co/dj/{slug}",
                },
                callback=self.parse_artist,
                meta={
                    "playwright": True,
                    "artist_slug": slug,
                    "depth": depth,
                    "event_type": event_type,
                    "event_limit": event_limit,
                    "max_artists": max_artists,
                },
            )

    def parse_artist(self, response):
        slug = response.meta["artist_slug"]
        depth = response.meta["depth"]
        event_type = response.meta["event_type"]
        event_limit = response.meta["event_limit"]
        max_artists = response.meta["max_artists"]
        max_depth = self._settings_int("MAX_DEPTH", 1)

        try:
            data = _json_from_response(response)
        except Exception as exc:
            log.error("Failed to parse response for '%s' (%s): %s", slug, event_type, exc)
            return

        errors = data.get("errors")
        if errors:
            log.warning("GraphQL errors for '%s' (%s): %s", slug, event_type, errors)
            return

        artist_data = (data.get("data") or {}).get("artist")
        if not artist_data:
            log.warning("No artist data for slug '%s'", slug)
            return

        artist_name = artist_data.get("name") or slug
        events = artist_data.get("events") or []
        log.info("[depth=%d] %s (%s): %d events", depth, artist_name, event_type, len(events))

        for event in events:
            event_id = event["id"]
            venue = event.get("venue") or {}
            area = venue.get("area") or {}
            date_raw = event.get("date", "")
            date = date_raw.split("T")[0] if "T" in date_raw else date_raw

            yield EventItem(
                id=f"{event_id}_{slug}",
                artist=artist_name,
                date=date,
                title=event.get("title"),
                link=f"https://ra.co/events/{event_id}",
                venue=venue.get("name"),
                city=area.get("name"),
            )

            lineup = [a["name"] for a in (event.get("artists") or []) if a.get("name")]
            if lineup:
                yield EventLineupItem(id=event_id, lineup=lineup)

            if depth < max_depth:
                for co in (event.get("artists") or []):
                    co_name = co.get("name")
                    if not co_name:
                        continue
                    co_slug = _name_to_slug(co_name)
                    if not co_slug or co_slug in self._queued:
                        continue
                    if len(self._queued) >= max_artists:
                        log.info("MAX_ARTISTS=%d reached, not queuing more", max_artists)
                        continue
                    self._queued.add(co_slug)
                    log.debug("Discovered: %s -> %s (depth %d)", co_name, co_slug, depth + 1)
                    yield from self._artist_requests(co_slug, depth + 1, event_limit, max_artists)
