# LOFI Artist Intelligence Platform — Development Plan

**Leading document:** LOFI Artist Intelligence route map (this plan follows its priorities 1–4)
**Reference only:** Talent Scout Systeem v2 (Matching Engine, Deal Flow/CRM, fee intelligence and rider management are out of scope; useful concepts such as hockey-stick detection and trajectory matching are absorbed where they overlap with the route map)
**Confirmed data assets:** Chartmetric API (planned), Resident Advisor scraper, Last.fm scraper, Partyflock scraper

---

## 1. What we are building

A proprietary intelligence system — not a database — that answers two questions:

1. **Who should we be paying attention to?** (detect emerging artists 6–18 months before the market)
2. **Can this artist actually sell tickets?** (evaluate established artists before booking decisions)

Every artist gets five scores: **Momentum, Growth, Market Relevance, Future Potential, Confidence.**

Guiding principle throughout: **growth acceleration beats current size.** All scoring and modeling decisions should be checked against this.

---

## 2. Data source mapping

How the confirmed assets cover the route map's required sources, and where the gaps are.

| Route map requirement | Covered by | Notes |
|---|---|---|
| Spotify (monthly listeners, followers, playlists, geo) | **Chartmetric** | Core source. Chartmetric also gives historical backfill — critical for training data |
| Instagram / TikTok / YouTube | **Chartmetric** | Follower counts, engagement, growth series |
| SoundCloud | **Chartmetric** | Plays/followers; verify coverage depth for underground artists |
| Beatport (charts, releases, labels) | **Chartmetric (partial)** | Chartmetric tracks Beatport charts; release/label metadata may need a supplementary Beatport scrape |
| Resident Advisor (events, lineups, attending) | **RA scraper** | Lineups, booking frequency, attending counts, venue capacities. One of the strongest early club-scene signals |
| Club & festival lineups | **RA scraper + Partyflock scraper** | Partyflock is the key NL/Amsterdam demand signal (event interest, lineups, local scene activity) |
| Listening trends / genre tags / similar artists | **Last.fm scraper** | Scrobble trends, tags for genre classification, similar-artist graph |
| Labels | **Gap (partial)** | Derive from Chartmetric/Beatport release metadata; maintain a curated label-tier list per sound framework |
| Agency representation | **Gap** | No API exists. Plan: periodic scrape of agency roster pages (The Team, WME, Prime Culture, etc.) + manual entry via the feedback interface. High value — agency moves are a top leading indicator |
| Playlist placements | **Chartmetric** | Editorial vs. algorithmic vs. user playlists distinguished |
| Podcast/radio validation (Boiler Room, RA Podcast, BBC R1) | **Gap** | Phase 2: scrape/track via YouTube (Boiler Room), RA, and curated event lists; also capturable as validation events via the feedback UI |
| Event announcements | **RA + Partyflock scrapers** | New-announcement diffing gives booking-momentum signal |

**Decision needed early:** Chartmetric plan tier — historical data depth and API rate limits determine how many artists can be tracked and how far back training data goes.

---

## 3. Phased plan

### Phase 0 — Foundations (Weeks 1–2)

- Repo, environments, cloud infrastructure (modest: one Postgres instance + scheduled workers is enough to start).
- **Storage:** PostgreSQL for entities (artists, events, labels, agencies, feedback) + TimescaleDB extension for all metric time series.
- **Orchestration:** scheduled pipeline runner (Airflow or simpler — Prefect/cron — given team size) for nightly pulls.
- **Canonical schema design**, the most important deliverable of this phase:
  - `artist` (canonical ID) ↔ per-source ID mappings (Chartmetric ID, RA slug, Partyflock ID, Last.fm name, Spotify ID)
  - `metric_observation` (artist_id, source, metric, value, observed_at) — append-only, never overwritten
  - `event` / `lineup_slot` (festival/club, capacity, billing position, date)
  - `validation_event` (typed milestones: first Boiler Room, first Ibiza booking, agency signing, etc.)
  - `feedback` (booking-team input, categorized)
  - `sound_framework` (config-driven: labels, festivals, agencies, media, benchmark artists per genre)

### Phase 1 — Data Foundation (Months 1–3) · *Route map Priority 1a*

Goal: reliable artist profiles, clean historical datasets, single source of truth — **before any model training.**

1. **Chartmetric integration first.** It covers the most required sources in one connection and provides historical backfill. Ingest: Spotify listeners/followers, IG/TikTok/YouTube, SoundCloud, playlists, Beatport charts, geo data.
2. **Harden the three scrapers** (RA, Partyflock, Last.fm): move them into the orchestrator, add retry/monitoring, normalize output into the canonical schema.
3. **Entity resolution** — the hardest and most underestimated problem. The same artist appears as different strings across RA, Partyflock, Last.fm and Chartmetric. Build a matching layer (Chartmetric IDs as anchor where possible, fuzzy matching + manual review queue for the rest). Budget real time for this; bad entity resolution silently poisons everything downstream.
4. **Data quality layer:** per-source freshness checks, anomaly flags on impossible jumps (scraper breakage vs. real spike), coverage dashboard (which artists have which sources).
5. **Point-in-time correctness:** store every observation with its timestamp and never backfill over it. This is what makes honest ML training possible later (no data leakage).
6. Seed the system with an initial roster: benchmark artists from the Tech-House framework (all tiers) + current LOFI bookings + a few hundred candidates from RA/Partyflock lineups.

**Exit criteria:** ~300–500 artists tracked with daily series from ≥3 sources, entity resolution >95% confident, 60+ days of clean history accumulating (plus Chartmetric backfill).

### Phase 2 — Agent Intelligence Layer, v1 heuristic scores (Months 3–5) · *Priority 1b*

Ship the five scores **rule-based first**, ML later. This delivers value immediately and produces the score history the ML model will need.

- **Growth Score:** MoM and 90-day growth across listeners/followers, weighted toward acceleration (second derivative — the "hockey stick" detector from the reference doc).
- **Momentum Score:** cross-source composite — streaming growth + RA attending growth + Partyflock interest + booking-frequency increase + new playlist adds. Cross-platform resonance weighted above single-platform spikes.
- **Market Relevance Score:** activity within the sound framework's ecosystem — bookings at relevant festivals/clubs, releases on relevant labels, geo growth in NL/EU.
- **Future Potential Score:** leading indicators — agency tier and upgrades, validation events, support slots for benchmark artists, tastemaker follows/mentions where available.
- **Confidence Score:** data coverage and freshness per artist (few sources or short history → low confidence).

Alongside the scores:

- **Sound framework engine:** frameworks live as config (DB/YAML), not code. Implement Tech-House/House fully (festivals, labels, agencies with the 10/8/6 tier scoring, media, podcasts tiers 1–3, benchmark artists A+/A/B) exactly as specified in the route map. New frameworks (Afro House, Melodic, UKG…) must be addable without architecture changes.
- **Validation event detection:** automatic where possible (first RA-listed Ibiza booking, first Boiler Room via YouTube, capacity-tier firsts from venue data, Beatport chart firsts), manual entry for the rest.
- **Genre-specific sub-scores** (Ecosystem, Ibiza, Industry Support, Agency Validation, Booking Momentum, Chart Performance, Label Validation, Podcast Validation, LOFI Fit) computed per framework.

**Exit criteria:** every tracked artist has the five scores + framework sub-scores, recomputed nightly, with score history stored.

### Phase 3 — ML Prediction Model (Months 5–8) · *Priority 1c*

Gradient boosting (XGBoost/LightGBM) predicting **future outcomes, not current popularity.**

1. **Define labels first** (the make-or-break step). Operationalize "breakout" at a 6–12 month horizon, e.g. any of: listener base ≥2.5×, agency tier upgrade, first headline above a capacity threshold, ≥N bookings at framework Tier-1 festivals. Use the route map's validation events as label components.
2. **Build the training set from history:** Chartmetric backfill + RA/Partyflock historical events let us snapshot artists "as of" past dates and check what happened 12 months later. Benchmark artists (Chris Stussy, Mau P, Kolter, Rossi., Josh Baker, PAWSA trajectories) are positive examples; same-era peers who plateaued are negatives.
3. **Features = the Phase 2 score inputs at point-in-time** (growth rates, acceleration, agency tier, validation-event counts, ecosystem activity, geo spread), strictly using only data observable at snapshot time.
4. **Two model targets:**
   - *Emerging:* breakout probability / future headliner potential / future booking demand.
   - *Established:* momentum trajectory (growing/stable/declining) and demand direction. (True ticket-sales prediction waits for Phase 6 when LOFI internal data lands.)
5. **Backtest before trusting:** time-based cross-validation, measure hit rate on held-out historical periods. Realistic target per the reference doc: ~50% → 65–75% hit rate as data matures. Report calibration, not just accuracy.
6. ML scores replace/blend with heuristic scores; heuristics remain as fallback for low-data artists (Confidence Score governs the blend).

### Phase 4 — Feedback Loop + Web Interface (Months 4–9, parallel) · *Priority 2*

Start the interface during Phase 2 — the booking team's usage generates the feedback data Priority 2 requires.

**Web app (React + FastAPI/Node over the same Postgres):**
- Artist profile pages: growth timeline, all scores + history, booking/festival history, label & agency affiliations, geo growth, similar artists, LOFI feedback history, and (after Phase 3) historical predictions vs. actual outcomes.
- Momentum dashboard + trend alerts feed.
- Search, advanced filtering (by framework, score range, agency tier, validation events), artist comparison (emerging vs. established within the same sound).

**Human feedback interface:**
- Track/untrack artists; manual score adjustments (logged as deltas, never overwriting model output).
- Qualitative notes ("big release coming", "stage full during opening set") — free text + structured tags.
- The six feedback categories from the route map: Fits LOFI / Doesn't Fit / Sound To Develop / Saturated / Interesting Support Act / Potential Future Headliner.
- Per-framework metric weighting controls for the booking team.

**Closing the loop (Priority 2's core):** feedback categories become ML features and label refinements; score adjustments are treated as supervised signal; quarterly retraining incorporates accumulated feedback so the model gradually learns how the LOFI team evaluates artists. Log every prediction with timestamp so model-vs-team disagreements become training material.

### Phase 5 — Trend Radar / Anomaly Detector (Months 8–10) · *Priority 3*

Built on the time-series foundation:
- **Artist-level anomalies:** growth spikes (z-score vs. own baseline), breakout tracks, sudden RA/Partyflock attention, new influential-DJ support, new festival/label support.
- **Market-level trends:** aggregate score and booking series per genre tag (Last.fm tags + framework membership) and per region → emerging/declining genre flags, regional shifts, emerging local scenes.
- **Alert outputs** matching the route map's language: "Pay attention to this artist now", "Potential breakout", "Momentum accelerating", "Genre trend emerging/declining" — delivered in-app + Slack/email.

### Phase 6 — LOFI Internal Data Integration (Months 10–12+) · *Priority 4*

- Ingest historical ticket sales, capacity performance, sell-out rates, event profitability, audience demographics, genre performance.
- Join to canonical artist IDs and event records.
- New model heads: **"Can this artist sell tickets in Amsterdam?"**, fee-vs-value assessment, audience-overlap ("do we already have this audience?"), under/overvalued artist screens, sound over/underperformance.
- This completes the long-term vision: Artist + Sound + Market + Booking Intelligence in one system.

---

## 4. Recommended stack

| Layer | Choice | Why |
|---|---|---|
| Ingestion | Python workers + Airflow/Prefect | Scheduled API pulls and scrapes, retries, monitoring |
| Storage | PostgreSQL + TimescaleDB | Entities + fast time-series queries on growth curves |
| Cache | Redis | Fast dashboard reads |
| ML | pandas, scikit-learn, XGBoost | Gradient boosting per route map; SHAP for explainable scores |
| API | FastAPI | Serves scores, profiles, alerts |
| Frontend | React + recharts | Dashboards, timelines, comparisons |
| Alerts | Slack webhook + email | Trend radar delivery |

---

## 5. Risks & mitigations

1. **Entity resolution debt** — mitigate with Chartmetric IDs as anchor, manual review queue, and resolving identity *before* accumulating history.
2. **Scraper fragility (RA/Partyflock)** — structural-change detection, alerting on volume drops, snapshot raw HTML for reprocessing.
3. **Too few training labels early** — heuristic scores carry the platform until ~12 months of point-in-time history + Chartmetric backfill make honest training possible; don't train prematurely on leaky data.
4. **Agency data has no API** — treat as semi-manual: roster scrapes + booking-team entry; the signal value justifies the effort.
5. **Chartmetric rate limits/cost** — tier the roster (daily refresh for tracked artists, weekly for the long tail).
6. **Model trust** — always show *why* a score is high (top SHAP features in the UI); the team stays the decision-maker, which also drives feedback volume.

---

## 6. Milestone summary

| When | Milestone |
|---|---|
| Month 1 | Schema live, Chartmetric flowing, scrapers in orchestrator |
| Month 3 | 300–500 artists with multi-source history; data-quality dashboard; entity resolution solid |
| Month 5 | Five heuristic scores + Tech-House framework live; first booking-team usage |
| Month 6–7 | Web interface + feedback loop in production |
| Month 8 | First ML model backtested and deployed (breakout probability) |
| Month 10 | Trend radar live with Slack alerts |
| Month 12 | LOFI ticket data integrated; "can this artist sell tickets in Amsterdam?" answerable |
| Month 12+ | Quarterly retrains; second and third sound frameworks added via config only |

**Success criterion (from the route map):** the platform surfaces the next Chris Stussy / Josh Baker / Kolter / Mau P before the wider market — measured by logging every high-score prediction with a timestamp and reviewing hit rate every quarter.
