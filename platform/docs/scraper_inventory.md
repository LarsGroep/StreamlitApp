# Scraper Inventory

Last updated: 2026-06-12

## Summary

Six Scrapy spiders in `ra-scraper-master/scraper/scraper/spiders/`. All output JSONL via `MyJsonLinesItemExporter`. Pipeline now opens files in **append mode** (`"ab"`) — safe to re-run without data loss.

---

## 1. `ra_artist_spider.py` — Resident Advisor Events

| Field | Detail |
|---|---|
| Input | `artists.txt` (seed list) |
| Output | `EventItem.jsonl`, `EventLineupItem.jsonl` |
| Current records | EventItem: 362, EventLineupItem: 362 |
| Transport | GraphQL API (`api.ra.co/graphql`) |
| Rate limiting | None explicit — Scrapy default concurrency |
| Fields captured | artist, date, title, venue, city, country, attending count, lineup array |
| Failures | Logs warnings on HTTP errors; no retry logic |
| Raw storage | **No** — parses directly to JSONL |

**Gap:** No rate-limit handling. No raw payload storage. `attending` field is the primary RA engagement signal — verify it's populated in all records.

---

## 2. `partyflock_spider.py` — Partyflock Artist Profiles

| Field | Detail |
|---|---|
| Input | `artists.txt` (or `artists_file` spider arg) |
| Output | `PartyflockArtistItem.jsonl`, `PartyflockEventItem.jsonl` |
| Current records | PartyflockArtistItem: **34** (743 missing — targeted re-scrape running) |
| Transport | HTML scraping (`partyflock.nl/artist/{slug}`) |
| Rate limiting | None explicit |
| Fields captured | fans, past/upcoming/total performances, photos, videos, vote_result, genres, last performance details, Partyflock artist ID |
| Failures | `errback_with_fallback` retries with strip-only slug; logs warning on final failure |
| Raw storage | **No** |
| Slug generation | NFKD normalization + `_CHAR_MAP` (ø→o, æ→ae, ß→ss, etc.) + `_SLUG_OVERRIDES` for edge cases |

**Encoding fix applied:** `file_io.py` `get_artists()` now opens `artists.txt` with `encoding="utf-8"` (was defaulting to `cp1252` on Windows, corrupting accented names before slug generation).

---

## 3. `partyflock_event_spider.py` — Partyflock Event Lineups

| Field | Detail |
|---|---|
| Input | Unique event URLs from `PartyflockEventItem.jsonl` |
| Output | `PartyflockLineupItem.jsonl` |
| Current records | 2,085 |
| Rate limiting | 8 concurrent, 0.25s delay, autothrottle enabled |
| Fields captured | event URL, event name, date, venue, city, country, lat/lon, full lineup array |
| Filter | Last 4 years only |
| Raw storage | **No** |

---

## 4. `partyflock_event_spider.py` archive (via `partyflock_spider.py`) — Historical Events

| Field | Detail |
|---|---|
| Output | `PartyflockEventItem.jsonl` |
| Current records | 9,342 |
| Fields captured | artist, partyflock_artist_id, event_name, event_url, start_date, venue, city, country, lat/lon |
| Source | `/artist/{id}/archive` pages |

---

## 5. `festival_spider.py` — Festival Lineups

| Field | Detail |
|---|---|
| Input | `festivals.json` (URL + CSS selectors per festival) |
| Output | `FestivalLineupItem.jsonl` |
| Current records | **15** (sparse — festivals.json needs populating) |
| Fields captured | festival_name, year, artist |
| Raw storage | **No** |

**Gap:** `festivals.json` has minimal entries. Needs to be populated with Circoloco, Music On, ANTS, PIV, Kappa FuturFestival, Sunwaves URLs + CSS selectors.

---

## 6. Last.fm Scraper (`lastfm/lastfm_scraper.py`)

| Field | Detail |
|---|---|
| Input | `artists.txt`, `similar_artists.txt`, `PartyflockArtistItem.jsonl` |
| Output | `lastfm/LastFMSnapshot.jsonl` (appended), `lastfm/features.csv` (overwritten) |
| Current records | LastFMSnapshot: 1,286 |
| Transport | Last.fm API (`artist.getInfo`) |
| Rate limiting | 0.22s per request (~4.5 req/s, under 5 req/s limit) |
| Fields captured | listeners, playcount, tags, similar artists, scraped_at |
| Time-series | **Yes** — each run appends a snapshot. Growth deltas computed when ≥2 snapshots exist |
| Raw storage | **No** — response parsed in-memory |

---

## Cross-cutting Gaps

| Gap | Priority | Plan |
|---|---|---|
| No raw response storage | High | `ingestion/` wrappers compress JSONL snapshot before parsing |
| `"wb"` overwrite mode | **Fixed** | Changed to `"ab"` in `pipelines.py` |
| No volume-drop alerts | Medium | `ingestion/quality.py` checks coverage per run |
| No structure-change detection | Medium | Add to `quality.py` Phase 1.7 |
| `festivals.json` underpopulated | Medium | Manual entry needed for framework festivals |
| No rate limiting on RA/Partyflock profile spiders | Low | Add `DOWNLOAD_DELAY` setting in `settings.py` |
