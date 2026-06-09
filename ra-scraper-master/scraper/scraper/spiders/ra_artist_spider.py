import json
import logging
import os

import scrapy

from scraper.items import EventItem, EventLineupItem
from scraper.utils.file_io import get_artists
from scraper.utils.logger import get_logger

log = get_logger(__name__)

_GRAPHQL_URL = "https://ra.co/graphql"

_ARTIST_EVENTS_QUERY = """
query GET_ARTIST_EVENTS($slug: String!, $limit: Int) {
  artist(slug: $slug) {
    id
    name
    events(limit: $limit, type: LATEST) {
      id
      date
      title
      venue {
        name
        area {
          name
        }
      }
      artists {
        name
      }
    }
  }
}
"""


def _json_from_response(response):
    """Playwright wraps raw JSON in <html><body><pre>...</pre></body>."""
    pre = response.css("pre ::text").get()
    if pre:
        return json.loads(pre)
    return json.loads(response.text)


def _graphql_meta(artist_slug):
    return {
        "playwright": True,
        "artist_slug": artist_slug,
    }


class RaArtistSpider(scrapy.Spider):
    name = "ra_artist_spider"
    allowed_domains = ["ra.co"]
    start_urls = []

    def __init__(self):
        if os.environ.get("SCRAPY_CHECK"):
            log.setLevel(logging.WARNING)

    def parse(self, response):
        slug = response.meta["artist_slug"]
        log.info("Parsing events for artist slug '%s'", slug)

        try:
            data = _json_from_response(response)
        except Exception as exc:
            log.error("Failed to parse GraphQL response for '%s': %s", slug, exc)
            return

        errors = data.get("errors")
        if errors:
            log.error("GraphQL errors for '%s': %s", slug, errors)
            return

        artist_data = (data.get("data") or {}).get("artist")
        if not artist_data:
            log.warning("No artist data returned for slug '%s'", slug)
            return

        artist_name = artist_data.get("name") or slug
        events = artist_data.get("events") or []
        log.info("Found %d events for %s", len(events), artist_name)

        for event in events:
            event_id = event["id"]
            venue = event.get("venue") or {}
            area = venue.get("area") or {}
            date_raw = event.get("date", "")
            date = date_raw.split("T")[0] if "T" in date_raw else date_raw

            yield EventItem(
                id=event_id,
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

    async def start(self):
        artists = get_artists("artists.txt")
        for artist in artists:
            body = json.dumps({
                "query": _ARTIST_EVENTS_QUERY,
                "variables": {"slug": artist, "limit": 20},
            }).encode()
            yield scrapy.Request(
                _GRAPHQL_URL,
                method="POST",
                body=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Origin": "https://ra.co",
                    "Referer": f"https://ra.co/dj/{artist}",
                },
                callback=self.parse,
                meta=_graphql_meta(artist),
            )
