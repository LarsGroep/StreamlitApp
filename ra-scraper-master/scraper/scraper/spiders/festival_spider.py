import hashlib
import json
import logging
import os
import re
from datetime import datetime

import scrapy

from scraper.items import FestivalLineupItem

log = logging.getLogger(__name__)

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "festivals.json")


def _item_id(festival: str, year: int, artist: str) -> str:
    raw = f"{festival}|{year}|{artist}".lower()
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _load_festivals() -> list[dict]:
    path = os.path.normpath(_CONFIG_PATH)
    if not os.path.exists(path):
        log.error("festivals.json not found at %s", path)
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class FestivalSpider(scrapy.Spider):
    name = "festival_spider"

    custom_settings = {
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy.core.downloader.handlers.http.HTTPDownloadHandler",
            "https": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
    }

    async def start(self):
        festivals = _load_festivals()
        if not festivals:
            log.warning("No festivals configured — add entries to festivals.json")
            return
        for festival in festivals:
            yield scrapy.Request(
                festival["lineup_url"],
                callback=self.parse,
                errback=self.errback,
                meta={"festival": festival},
                headers={"User-Agent": "Mozilla/5.0 (compatible; lofi-research-bot/1.0)"},
            )

    def parse(self, response):
        festival = response.meta["festival"]
        name = festival["name"]
        year = festival["year"]
        selectors = festival.get("artist_selectors", [])
        href_pattern = festival.get("href_pattern")

        artists: list[str] = []

        if href_pattern:
            seen: set[str] = set()
            for a in response.css(f"a[href*='{href_pattern}']"):
                href = a.attrib.get("href", "")
                m = re.search(rf"{re.escape(href_pattern)}([^/]+)/", href)
                if m:
                    slug = m.group(1).replace("-", " ").title()
                    if slug not in seen:
                        seen.add(slug)
                        artists.append(slug)
            if artists:
                log.info("Festival '%s': href_pattern matched %d artists", name, len(artists))

        if not artists:
            for selector in selectors:
                found = [t.strip() for t in response.css(f"{selector}::text").getall() if t.strip()]
                if found:
                    artists = found
                    log.info("Festival '%s': selector '%s' matched %d artists", name, selector, len(found))
                    break

        if not artists:
            log.warning(
                "Festival '%s': no artists found at %s — check selectors in festivals.json",
                name, response.url,
            )
            return

        scraped_at = datetime.utcnow().isoformat()
        for artist in artists:
            yield FestivalLineupItem(
                id=_item_id(name, year, artist),
                festival_name=name,
                festival_year=year,
                artist=artist,
                scraped_at=scraped_at,
            )

        log.info("Festival '%s' %d: scraped %d artists", name, year, len(artists))

    def errback(self, failure):
        festival = failure.request.meta.get("festival", {})
        log.warning("Request failed for festival '%s': %s", festival.get("name"), failure.value)
