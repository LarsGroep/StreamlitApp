import hashlib
import json
import logging
import os
import re
from datetime import datetime

import scrapy

from scraper.items import PartyflockLineupItem

log = logging.getLogger(__name__)

_BASE = "https://partyflock.nl"
_JSONL_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "PartyflockEventItem.jsonl")
)


def _event_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


_CUTOFF_YEAR = datetime.utcnow().year - 4  # only events from the last 4 years


def _load_unique_event_urls() -> list[dict]:
    """Read PartyflockEventItem.jsonl and return deduplicated events from the last 5 years."""
    if not os.path.exists(_JSONL_PATH):
        log.error("PartyflockEventItem.jsonl not found — run partyflock_spider first")
        return []
    seen: set[str] = set()
    events: list[dict] = []
    skipped = 0
    with open(_JSONL_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = item.get("event_url")
            if not url or url in seen:
                continue
            start = item.get("start_date") or ""
            try:
                year = int(start[:4])
            except (ValueError, TypeError):
                year = 0
            if year < _CUTOFF_YEAR:
                skipped += 1
                continue
            seen.add(url)
            events.append({
                "url": url,
                "city": item.get("city"),
                "country": item.get("country"),
            })
    log.info("Loaded %d unique events (skipped %d before %d)", len(events), skipped, _CUTOFF_YEAR)
    return events


class PartyflockEventSpider(scrapy.Spider):
    name = "partyflock_event_spider"
    allowed_domains = ["partyflock.nl"]

    custom_settings = {
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
            "https": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
        },
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.25,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 6,
    }

    async def start(self):
        events = _load_unique_event_urls()
        if not events:
            return
        log.info("Queuing %d unique Partyflock event pages", len(events))
        for ev in events:
            yield scrapy.Request(
                ev["url"],
                callback=self.parse_event,
                errback=self.errback,
                meta={"city": ev["city"], "country": ev["country"]},
                headers={"User-Agent": "Mozilla/5.0 (compatible; lofi-research-bot/1.0)"},
            )

    def parse_event(self, response):
        url = response.url

        # Event name from h1
        name_m = re.search(r'<h1[^>]*itemprop="name">([^<]+)<', response.text)
        event_name = name_m.group(1).strip() if name_m else None

        # Start date from first <time datetime="..."> tag
        date_m = re.search(r'<time[^>]+datetime="([^"]+)"', response.text)
        start_date = date_m.group(1) if date_m else None

        # Venue
        venue_m = re.search(
            r'itemprop="location".*?itemprop="name">([^<]+)<',
            response.text, re.DOTALL
        )
        venue = venue_m.group(1).strip() if venue_m else None

        # City / country from meta passed through or from page
        city = response.meta.get("city")
        country = response.meta.get("country")
        if not city:
            city_m = re.search(r'itemprop="addressLocality"[^>]*content="([^"]+)"', response.text)
            city = city_m.group(1) if city_m else None

        # Full lineup via Schema.org performer itemprop
        lineup = re.findall(
            r'itemprop="performer"[^>]*>.*?itemprop="name">([^<]+)</span>',
            response.text, re.DOTALL,
        )
        lineup = [html_unescape(a) for a in lineup if a.strip()]

        if not lineup:
            log.debug("No lineup found at %s", url)
            return

        yield PartyflockLineupItem(
            id=_event_id(url),
            event_url=url,
            event_name=event_name,
            start_date=start_date,
            venue=venue,
            city=city,
            country=country,
            lineup=lineup,
            scraped_at=datetime.utcnow().isoformat(),
        )

    def errback(self, failure):
        log.debug("Failed: %s", failure.request.url)


def html_unescape(text: str) -> str:
    return (text
            .replace("&amp;", "&")
            .replace("&#039;", "'")
            .replace("&quot;", '"')
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&#216;", "Ø")
            .replace("&#248;", "ø")
            .replace("&#229;", "å")
            .replace("&#230;", "æ")
            .replace("&#233;", "é")
            .replace("&#232;", "è")
            .replace("&#246;", "ö")
            .replace("&#228;", "ä")
            .replace("&#252;", "ü")
            .replace("&#223;", "ß")
            )
