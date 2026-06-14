import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timezone

import scrapy

from scraper.items import ArtistBillingItem, EventItem, EventLineupItem
from scraper.utils.file_io import get_artists
from scraper.utils.logger import get_logger

log = get_logger(__name__)


def _ra_slug(name: str) -> str:
    """Convert display name to RA slug: lowercase, strip accents, remove all non-alphanumeric."""
    normalized = unicodedata.normalize("NFD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", ascii_name.lower())

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
      contentUrl
      venue {
        name
        capacity
        area {
          name
          country {
            name
          }
        }
      }
      artists {
        name
        headliner
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

        scraped_at = datetime.now(timezone.utc).isoformat()

        for event in events:
            event_id = event["id"]
            venue = event.get("venue") or {}
            area = venue.get("area") or {}
            country_data = area.get("country") or {}
            date_raw = event.get("date", "")
            date = date_raw.split("T")[0] if "T" in date_raw else date_raw
            event_url = f"https://ra.co{event.get('contentUrl', '')}" if event.get("contentUrl") else f"https://ra.co/events/{event_id}"

            yield EventItem(
                id=event_id,
                artist=artist_name,
                date=date,
                title=event.get("title"),
                link=event_url,
                venue=venue.get("name"),
                city=area.get("name"),
            )

            artists_on_bill = event.get("artists") or []
            lineup = [a["name"] for a in artists_on_bill if a.get("name")]
            headliner_names = [a["name"] for a in artists_on_bill if a.get("name") and a.get("headliner")]

            if lineup:
                yield EventLineupItem(id=event_id, lineup=lineup)

            # Yield billing data for every event so the aggregator can compute
            # headline count, festival count, Tier-A co-billing per artist.
            is_headliner = artist_name in headliner_names
            yield ArtistBillingItem(
                id=f"{slug}::{event_id}",
                artist=artist_name,
                ra_slug=slug,
                event_id=str(event_id),
                event_url=event_url,
                date=date,
                title=event.get("title"),
                venue=venue.get("name"),
                city=area.get("name"),
                country=country_data.get("name"),
                venue_capacity=venue.get("capacity"),
                lineup=lineup,
                headliner_names=headliner_names,
                is_headliner=is_headliner,
                lineup_size=len(lineup),
                scraped_at=scraped_at,
            )

    async def start(self):
        artists = get_artists("artists.txt")
        for artist in artists:
            slug = _ra_slug(artist)
            body = json.dumps({
                "query": _ARTIST_EVENTS_QUERY,
                "variables": {"slug": slug, "limit": 200},
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
                callback=self.parse,
                meta=_graphql_meta(slug),
            )
