import hashlib
import logging
import re
import unicodedata
from datetime import datetime

import scrapy

from scraper.items import PartyflockArtistItem, PartyflockEventItem
from scraper.utils.file_io import get_artists

log = logging.getLogger(__name__)

_BASE = "https://partyflock.nl"

# Characters that NFKD does not decompose — map to ASCII equivalents
_CHAR_MAP = {
    ord("ø"): "o",   # Scandinavian o-stroke
    ord("Ø"): "o",
    ord("æ"): "ae",  # ae-ligature
    ord("Æ"): "ae",
    ord("ß"): "ss",  # German eszett
    ord("œ"): "oe",
    ord("Œ"): "oe",
    ord("ʼ"): "",    # modifier apostrophe (e.g. Samaʼ Abdulhadi)
    ord("’"): "",  # right single quotation mark
    ord("‘"): "",  # left single quotation mark
}

# Artists whose slugs cannot be derived algorithmically
_SLUG_OVERRIDES = {
    "ø [phase]": "phase",
    "âme": "me",     # Partyflock indexed them as "Me"
}


def _slug(name: str) -> str:
    """Primary slug: transliterate diacritics to ASCII equivalents."""
    key = name.lower().strip()
    if key in _SLUG_OVERRIDES:
        return _SLUG_OVERRIDES[key]
    name = name.translate(_CHAR_MAP)
    normalized = unicodedata.normalize("NFKD", name.lower())
    ascii_name = "".join(c for c in normalized if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_")


def _slug_strip(name: str) -> str:
    """Fallback slug: strip all non-ASCII (original behaviour)."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _parse_int(text: str) -> int | None:
    cleaned = re.sub(r"[^\d]", "", text)
    return int(cleaned) if cleaned else None


def _item_id(artist: str) -> str:
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    raw = f"{artist.lower()}|{date_str}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _event_id(artist: str, event_url: str) -> str:
    raw = f"{artist.lower()}|{event_url}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


class PartyflockSpider(scrapy.Spider):
    name = "partyflock_spider"
    allowed_domains = ["partyflock.nl"]

    custom_settings = {
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
            "https": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
        },
    }

    async def start(self):
        artists_file = getattr(self, "artists_file", "artists.txt")
        artists = get_artists(artists_file)
        for artist in artists:
            slug = _slug(artist)
            alt = _slug_strip(artist)
            url = f"{_BASE}/artist/{slug}"
            yield scrapy.Request(
                url,
                callback=self.parse_profile,
                errback=self.errback_with_fallback,
                meta={"artist": artist, "alt_slug": alt if alt != slug else None},
                headers={"User-Agent": "Mozilla/5.0 (compatible; lofi-research-bot/1.0)"},
            )

    def parse_profile(self, response):
        artist = response.meta["artist"]

        # Extract canonical Partyflock artist ID from archive link
        m = re.search(r"/artist/(\d+)/archive", response.text)
        artist_id = m.group(1) if m else None

        stats: dict = {
            "fans": None, "total": None, "upcoming": None, "past": None,
            "views": None, "views_since": None, "photos": None, "videos": None,
            "vote_result": None, "vote_count": None,
        }

        for tr in response.css("table.default tr"):
            cells = [c.css("::text").get("").strip() for c in tr.css("td")]
            cells = [c for c in cells if c and c not in ("·", "×", "")]
            if len(cells) < 2:
                continue
            value_raw = cells[0]
            label = " ".join(cells[1:]).lower()

            if "fans" in label:
                stats["fans"] = _parse_int(value_raw) if value_raw != "geen" else 0
            elif "in de toekomst" in label:
                stats["upcoming"] = _parse_int(value_raw) if value_raw != "geen" else 0
            elif "in het verleden" in label:
                stats["past"] = _parse_int(value_raw) if value_raw != "geen" else 0
            elif "optredens" in label and "verleden" not in label and "toekomst" not in label:
                stats["total"] = _parse_int(value_raw) if value_raw != "geen" else 0
            elif "bekeken" in label:
                stats["views"] = _parse_int(value_raw)
                since_m = re.search(r"sinds\s+(.+)", label)
                stats["views_since"] = since_m.group(1).strip() if since_m else None
            elif "foto" in label:
                stats["photos"] = _parse_int(value_raw) if value_raw != "geen" else 0
            elif "video" in label:
                stats["videos"] = _parse_int(value_raw) if value_raw != "geen" else 0
            elif "stemresultaat" in label:
                stats["vote_result"] = value_raw
                vc = re.search(r"\((\d+)\s+stemmen\)", label)
                stats["vote_count"] = int(vc.group(1)) if vc else None

        genres = response.css("a[href*='/agenda/genre/']::attr(href)").getall()
        genres = [g.split("/agenda/genre/")[-1] for g in genres]

        # Last performance
        last_m = re.search(
            r"Laatste optreden[^:]*:.*?<b><a[^>]*>([^<]+)</a></b>,\s*"
            r"<a[^>]*>([^<]+)</a>,\s*<a[^>]*>([^<]+)</a>",
            response.text,
        )
        last_date_m = re.search(r"Laatste optreden was op [a-z]+ (\d{1,2} \w+ \d{4})", response.text)

        if all(v is None for v in stats.values()):
            log.warning("No stats found for '%s' at %s", artist, response.url)
            return

        log.info("Partyflock '%s' (id=%s): fans=%s upcoming=%s past=%s genres=%s",
                 artist, artist_id, stats["fans"], stats["upcoming"], stats["past"], genres)

        yield PartyflockArtistItem(
            id=_item_id(artist),
            artist=artist,
            partyflock_url=response.url,
            partyflock_artist_id=artist_id,
            fans=stats["fans"],
            total_performances=stats["total"],
            upcoming_performances=stats["upcoming"],
            past_performances=stats["past"],
            views=stats["views"],
            views_since=stats["views_since"],
            photos=stats["photos"],
            videos=stats["videos"],
            vote_result=stats["vote_result"],
            vote_count=stats["vote_count"],
            genres=genres,
            last_performance_date=last_date_m.group(1) if last_date_m else None,
            last_performance_event=last_m.group(1) if last_m else None,
            last_performance_venue=last_m.group(2) if last_m else None,
            last_performance_city=last_m.group(3) if last_m else None,
            scraped_at=datetime.utcnow().isoformat(),
        )

        # Follow to archive for time series events
        if artist_id:
            yield scrapy.Request(
                f"{_BASE}/artist/{artist_id}/archive",
                callback=self.parse_archive,
                errback=self.errback,
                meta={"artist": artist, "artist_id": artist_id},
                headers={"User-Agent": "Mozilla/5.0 (compatible; lofi-research-bot/1.0)"},
            )

    def parse_archive(self, response):
        artist = response.meta["artist"]
        artist_id = response.meta["artist_id"]
        scraped_at = datetime.utcnow().isoformat()

        event_blocks = re.findall(
            r'itemprop="performerIn"[^>]*>(.*?)</tbody>',
            response.text,
            re.DOTALL,
        )

        for block in event_blocks:
            start_m = re.search(r'itemprop="startDate" content="([^"]+)"', block)
            name_m = re.search(r'itemprop="name">([^<]+)</span>', block)
            url_m = re.search(r'href="(/party/[^"]+)"', block)
            venue_m = re.search(r'itemprop="name" content="([^"]+)"', block)
            city_m = re.search(r'itemprop="addressLocality" content="([^"]+)"', block)
            country_m = re.search(r'itemprop="alternateName" content="([^"]+)"', block)
            lat_m = re.search(r'itemprop="latitude" content="([^"]+)"', block)
            lon_m = re.search(r'itemprop="longitude" content="([^"]+)"', block)

            start_date = start_m.group(1) if start_m else None
            event_url = (_BASE + url_m.group(1)) if url_m else None
            if not start_date or not event_url:
                continue

            yield PartyflockEventItem(
                id=_event_id(artist, event_url),
                artist=artist,
                partyflock_artist_id=artist_id,
                event_name=name_m.group(1) if name_m else None,
                event_url=event_url,
                start_date=start_date,
                venue=venue_m.group(1) if venue_m else None,
                city=city_m.group(1) if city_m else None,
                country=country_m.group(1) if country_m else None,
                latitude=float(lat_m.group(1)) if lat_m else None,
                longitude=float(lon_m.group(1)) if lon_m else None,
                scraped_at=scraped_at,
            )

        log.info("Partyflock archive '%s': %d events scraped", artist, len(event_blocks))

    def errback_with_fallback(self, failure):
        artist = failure.request.meta.get("artist", "?")
        alt_slug = failure.request.meta.get("alt_slug")
        if alt_slug:
            log.info("Partyflock: retrying '%s' with fallback slug '%s'", artist, alt_slug)
            yield scrapy.Request(
                f"{_BASE}/artist/{alt_slug}",
                callback=self.parse_profile,
                errback=self.errback,
                meta={"artist": artist},
                headers={"User-Agent": "Mozilla/5.0 (compatible; lofi-research-bot/1.0)"},
            )
        else:
            log.warning("Partyflock: no page found for '%s' (%s)", artist, failure.request.url)

    def errback(self, failure):
        artist = failure.request.meta.get("artist", "?")
        log.warning("Partyflock: no page found for '%s' (%s)", artist, failure.request.url)
