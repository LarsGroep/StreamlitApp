"""
Beatport Label Spider (v2).

Scrapes the releases page for each framework label on Beatport, extracting
the roster of artists who have released on that label.

The releases are NOT in __NEXT_DATA__ — they're loaded via a client-side call to
  https://api.beatport.com/v4/catalog/releases/?label_id={id}&per_page=100
which requires a Bearer token (anon session). That token is provided in the
_next/data SSR response as pageProps.anonSession.access_token.

Strategy:
  1. Load label page with Playwright (gets cf_clearance + anon token).
  2. Intercept the _next/data response to extract the anonSession Bearer token
     and the real label ID.
  3. Use page.evaluate(fetch(...)) from within the browser context so that
     cookies (including cf_clearance) are forwarded for all pagination calls.

Input:  input/framework_labels.json  (list of {name, slug, id, framework, tier})
Output: BeatportLabelArtistItem.jsonl

Usage:
    cd scraper && scrapy crawl beatport_labels
    cd scraper && scrapy crawl beatport_labels -a labels_file=../input/framework_labels.json
"""

import asyncio
import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import scrapy

from scraper.items import BeatportLabelArtistItem

log = logging.getLogger(__name__)

_BASE = "https://www.beatport.com"
_API = "https://api.beatport.com"
_INPUT = Path(__file__).parent.parent.parent / "input" / "framework_labels.json"
_PER_PAGE = 100
_MAX_PAGES = 10  # up to 1000 releases per label


def _load_labels(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _item_id(label_slug: str, artist_name: str) -> str:
    raw = f"bp_label|{label_slug}|{artist_name.lower()}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


# JS snippet run inside the Playwright page that fetches all release pages
# and returns artist counts as {name: {count, artist_id, latest}}.
_FETCH_ALL_RELEASES_JS = """
async ([labelId, token, perPage, maxPages]) => {
    const base = 'https://api.beatport.com/v4/catalog/releases/';
    const headers = {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/json',
    };
    const artists = {};

    const accumulate = (results) => {
        for (const rel of results) {
            const date = rel.publish_date || rel.date || rel.new_release_date || null;
            for (const a of (rel.artists || [])) {
                if (!a.name) continue;
                if (!artists[a.name]) {
                    artists[a.name] = {count: 0, artist_id: a.id || null, latest: null};
                }
                artists[a.name].count += 1;
                if (a.id) artists[a.name].artist_id = a.id;
                if (date && (!artists[a.name].latest || date > artists[a.name].latest)) {
                    artists[a.name].latest = date;
                }
            }
        }
    };

    // Page 1
    const url1 = `${base}?page=1&per_page=${perPage}&order_by=-release_date,id&label_id=${labelId}`;
    let resp = await fetch(url1, {headers});
    if (!resp.ok) return {error: `page1 status ${resp.status}`, artists: {}};
    let data = await resp.json();
    const total = data.count || 0;
    accumulate(data.results || []);

    // Remaining pages
    const totalPages = Math.min(maxPages, Math.ceil(total / perPage));
    for (let p = 2; p <= totalPages; p++) {
        const url = `${base}?page=${p}&per_page=${perPage}&order_by=-release_date,id&label_id=${labelId}`;
        resp = await fetch(url, {headers});
        if (!resp.ok) break;
        data = await resp.json();
        accumulate(data.results || []);
    }

    return {total, pages: totalPages, artists};
}
"""


class BeatportLabelSpider(scrapy.Spider):
    name = "beatport_labels"

    custom_settings = {
        "DOWNLOAD_DELAY": 5.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 0.5,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 45000,
        "CONCURRENT_REQUESTS": 1,
    }

    def __init__(self, labels_file=None, **kwargs):
        super().__init__(**kwargs)
        path = Path(labels_file) if labels_file else _INPUT
        self._labels = _load_labels(path)
        log.info("Loaded %d labels from %s", len(self._labels), path)

    async def start(self):
        for label in self._labels:
            url = f"{_BASE}/label/{label['slug']}/{label['id']}/releases"
            yield scrapy.Request(
                url,
                callback=self.parse_label,
                meta={
                    "label": label,
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_init_callback": "init_page",
                },
            )

    @staticmethod
    async def init_page(page, request, spider):
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

    async def parse_label(self, response):
        label = response.meta["label"]
        page = response.meta["playwright_page"]

        # Wait for the page to make its own API calls (token gets set up)
        await asyncio.sleep(4)

        # Check for 404 or Cloudflare challenge
        page_title = await page.title()
        if "404" in page_title:
            log.error(
                "Label '%s' (id=%s) returned 404 — ID is likely wrong. "
                "Check https://www.beatport.com/label/%s/<ID>/releases",
                label["name"], label["id"], label["slug"],
            )
            await page.close()
            return
        if "Just a moment" in page_title:
            log.warning(
                "Label '%s' (id=%s) hit Cloudflare challenge — skipping",
                label["name"], label["id"],
            )
            await page.close()
            return

        # Extract anon token from window.__NEXT_DATA__
        token = None
        real_label_id = label["id"]

        try:
            next_data = await page.evaluate(
                "() => window.__NEXT_DATA__ ? JSON.parse(JSON.stringify(window.__NEXT_DATA__)) : null"
            )
            if next_data:
                pp = (next_data.get("props") or {}).get("pageProps") or {}
                anon_session = pp.get("anonSession") or {}
                token = anon_session.get("access_token")
                label_data = pp.get("label") or {}
                page_label_id = label_data.get("id")
                page_label_name = page_title.replace(" | Beatport", "").strip()
                if page_label_id:
                    real_label_id = page_label_id
                if page_label_name and page_label_name.lower() != label["name"].lower():
                    log.warning(
                        "Label '%s' (id=%s): page shows '%s' — ID may be wrong",
                        label["name"], label["id"], page_label_name,
                    )
                else:
                    log.info(
                        "Label '%s' (id=%s): page confirmed OK",
                        label["name"], real_label_id,
                    )
        except Exception as exc:
            log.warning("Could not extract token for '%s': %s", label["name"], exc)

        if not token:
            log.error("No anon token for label '%s' — skipping", label["name"])
            await page.close()
            return

        log.info(
            "Label '%s' (id=%s): fetching releases via v4 API...",
            label["name"], real_label_id,
        )

        try:
            result = await page.evaluate(
                _FETCH_ALL_RELEASES_JS,
                [real_label_id, token, _PER_PAGE, _MAX_PAGES],
            )
        except Exception as exc:
            log.error("JS eval failed for '%s': %s", label["name"], exc)
            await page.close()
            return

        await page.close()

        if result.get("error"):
            log.error("API error for '%s': %s", label["name"], result["error"])
            return

        artists = result.get("artists") or {}
        total = result.get("total", 0)
        pages = result.get("pages", 0)
        log.info(
            "Label '%s': %d releases across %d pages → %d unique artists",
            label["name"], total, pages, len(artists),
        )

        for item in self._emit_artists(label, artists):
            yield item

    def _emit_artists(self, label: dict, artists: dict):
        scraped_at = datetime.utcnow().isoformat()
        for artist_name, entry in artists.items():
            yield BeatportLabelArtistItem(
                id=_item_id(label["slug"], artist_name),
                label_name=label["name"],
                label_slug=label["slug"],
                label_id=label.get("id"),
                framework=label.get("framework"),
                tier=label.get("tier"),
                artist_name=artist_name,
                artist_id=entry.get("artist_id"),
                release_count=entry["count"],
                latest_release=entry.get("latest"),
                scraped_at=scraped_at,
            )
        log.info("Label '%s': emitted %d artists", label["name"], len(artists))
