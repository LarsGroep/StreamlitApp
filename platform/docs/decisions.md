# Decision Log

Format: `YYYY-MM-DD — Decision — Reason`

---

## 2026-06-12 — Put all platform code in `/platform` subfolder
Existing scrapers live in `ra-scraper-master/`. New infrastructure (schema, ingestion, scoring, ML, API) goes in `platform/` at repo root. Scrapers stay in place; `ingestion/` wrappers read their JSONL output.

## 2026-06-12 — Fix JSONL pipeline to append mode (`"ab"`)
`MyJsonLinesItemExporter` was opening files in `"wb"` (overwrite). Changed to `"ab"`. Added `DuplicatesPipeline.open_spider()` to pre-load existing IDs so re-runs don't create duplicates.

## 2026-06-12 — UTF-8 encoding fix in `file_io.py`
`get_artists()` was opening `artists.txt` without explicit encoding. On Windows this defaulted to `cp1252`, corrupting accented artist names (e.g. `Kléo` → `KlÃ©o`) before slug generation, causing Partyflock lookups to fail silently. Fixed with `encoding="utf-8"`.

## 2026-06-12 — `partyflock_spider.py` accepts `artists_file` spider argument
Enables targeted re-scrapes (`scrapy crawl partyflock_spider -a artists_file=missing_artists.txt`) without modifying the source. Default remains `artists.txt`.

## 2026-06-12 — LOFI booking history as ground-truth labels
755 artists from `lofi_events_raw.tsv` (2024–2026 events) added as `lofi_booked=1` labels in `lofi_booked_labels.csv`. Stored in `metric_observation` as `source="lofi_internal"` during seed step. These are the primary positive training examples for the ML model.

## 2026-06-12 — Chartmetric ID as entity resolution anchor
When available, Chartmetric ID is the definitive cross-source identifier. Fuzzy name matching (rapidfuzz, threshold 0.85) used as fallback. Unresolved artists go to `resolution_queue`, never silently into artist history (Principle #2).

## 2026-06-12 — TimescaleDB hypertable for `metric_observation`
All time-series metrics land in one append-only hypertable partitioned by `observed_at`. Enables efficient range queries for scoring (rolling 90-day windows) and ML (point-in-time feature extraction). Never backfill over existing observations (Principle #1).

## 2026-06-12 — Sound frameworks are YAML config seeded into DB
`scoring/frameworks/tech_house.yaml` → loaded by `seed_frameworks.py` into `sound_framework` + related tables. Adding a new genre framework requires zero code changes (Principle #4). Tech-House/House implemented first per route map.

## 2026-06-12 — Chartmetric as primary data stream
All streaming, social, geo, playlist and chart data flows through Chartmetric API (ingest_chartmetric.py). Last.fm and Partyflock remain as supplementary signals. Chartmetric metrics use `cm_` prefix in metric_observation.

## 2026-06-12 — EBM + XGBoost trained in parallel for comparison
Both ExplainableBoostingClassifier (EBM) and XGBoost are trained and saved as separate model files (breakout_ebm.pkl, breakout_xgb.pkl, etc.). EBM is the primary model for the UI (glass-box: feature contributions are exact, not SHAP approximations). XGBoost runs as comparison. The comparison_report.json in models/ records which performs better after each training run.

## 2026-06-12 — LOFI feel similarity target: < 100k Spotify monthly listeners
From the route map: target is artists "6-18 months before the wider market" — specifically the Tier B / pre-Tier-B range (Toman, Julian Fijma, Luuk van Dijk profile). 100k listeners is the discovery boundary. Similarity is computed as cosine distance to the 755 LOFI-booked artist centroid. Listener count excluded from the similarity feature vector so popularity doesn't dominate sound/scene fit.

## 2026-06-12 — Heuristic scores before ML (Principle #6)
`scoring/engine.py` implements all five scores rule-based. ML training blocked until ≥60 days of point-in-time history accumulate from the DB (not the flat JSONL files). The `confidence_score` metric governs how much weight the ML blend will receive vs. heuristics.
