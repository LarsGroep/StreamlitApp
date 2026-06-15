"""
RA Label Spider (v2).

Scrapes RA label pages to extract the roster of artists who have released on
each framework label. RA label pages load via GraphQL.

Input:  input/ra_labels.json  (list of {name, slug, framework, tier})
Output: RALabelArtistItem.jsonl

Usage:
    cd scraper && scrapy crawl ra_labels
    cd scraper && scrapy crawl ra_labels -a labels_file=../input/ra_labels.json
"""

import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import scrapy

from scraper.items import RALabelArtistItem

log = logging.getLogger(__name__)

_GRAPHQL = "https://ra.co/graphql"
_BASE = "https://ra.co"
_INPUT = Path(__file__).parent.parent.parent / "input" / "ra_labels.json"

_LABEL_RELEASES_QUERY = """
query GET_LABEL_RELEASES($slug: String!, $limit: Int, $page: Int) {
  label(slug: $slug) {
    id
    name
    releases(limit: $limit, page: $page) {
      id
      title
      date
      artists {
        name
      }
    }
    releasesCount
  }
}
"""

_PAGE_SIZE = 50
_MAX_PAGES = 10


def _load_labels(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _item_id(label_slug: str, artist_name: str) -> str:
    raw = f"ra_label|{label_slug}|{artist_name.lower()}"
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


class RALabelSpider(scrapy.Spider):
    name = "ra_labels"
    allowed_domains = ["ra.co"]

    def __init__(self, labels_file=None, **kwargs):
        super().__init__(**kwargs)
        path = Path(labels_file) if labels_file else _INPUT
        self._labels = _load_labels(path)
        log.info("Loaded %d RA labels from %s", len(self._labels), path)

    async def start(self):
        for label in self._labels:
            for req in self._page_request(label, page=1, aggregated=defaultdict(int)):
                yield req

    def _page_request(self, label: dict, page: int, aggregated: dict):
        body = json.dumps({
            "query": _LABEL_RELEASES_QUERY,
            "variables": {
                "slug": label["slug"],
                "limit": _PAGE_SIZE,
                "page": page,
            },
        }).encode()
        yield scrapy.Request(
            _GRAPHQL,
            method="POST",
            body=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://ra.co",
                "Referer": f"{_BASE}/labels/{label['slug']}",
            },
            callback=self.parse_label,
            meta={"label": label, "page": page, "aggregated": aggregated, "playwright": False},
        )

    def parse_label(self, response):
        label = response.meta["label"]
        page = response.meta["page"]
        aggregated: dict = response.meta["aggregated"]

        try:
            data = _json_from(response)
        except Exception as exc:
            log.error("JSON error for label '%s': %s", label["name"], exc)
            yield from self._emit(label, aggregated)
            return

        label_data = (data.get("data") or {}).get("label")
        if not label_data:
            log.warning(
                "No label data for '%s' — slug may not exist on RA. Try: %s/labels/%s",
                label["name"], _BASE, label["slug"],
            )
            yield from self._emit(label, aggregated)
            return

        releases = label_data.get("releases") or []
        total = label_data.get("releasesCount") or 0
        log.info("Label '%s' page %d: %d releases (total=%d)", label["name"], page, len(releases), total)

        for release in releases:
            for artist in (release.get("artists") or []):
                name = artist.get("name")
                if name:
                    aggregated[name] += 1

        next_offset = page * _PAGE_SIZE
        if releases and next_offset < total and page < _MAX_PAGES:
            yield from self._page_request(label, page + 1, aggregated)
        else:
            yield from self._emit(label, aggregated)

    def _emit(self, label: dict, aggregated: dict):
        scraped_at = datetime.utcnow().isoformat()
        for artist_name, count in aggregated.items():
            yield RALabelArtistItem(
                id=_item_id(label["slug"], artist_name),
                label_name=label["name"],
                label_slug=label["slug"],
                artist_name=artist_name,
                release_count=count,
                scraped_at=scraped_at,
            )
        log.info("Label '%s': emitted %d artists", label["name"], len(aggregated))
