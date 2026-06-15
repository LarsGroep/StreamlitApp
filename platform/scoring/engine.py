"""
Heuristic scoring engine — computes the five scores for every tracked artist.
All scores are written to metric_observation with source='scoring_engine'.

Scores (0-100):
  - growth_score          MoM + 90d acceleration (second derivative weighted 2x)
  - momentum_score        Cross-source composite: streams + events + fans
  - market_relevance      Framework ecosystem activity + geo presence
  - future_potential      Agency tier + validation events + benchmark co-appearances
  - confidence_score      Data coverage × history length (0-1, stored as 0-100)

Run nightly:
    python -m scoring.engine
"""

import math
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from schema.database import get_session
from schema.models import (
    Artist, FrameworkAgency, FrameworkArtist, LineupSlot,
    MetricObservation, SoundFramework, ValidationEvent,
)

SOURCES = ("lastfm", "partyflock", "ra", "chartmetric")
MIN_HISTORY_DAYS = 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_series(session: Session, artist_id, source: str, metric: str, days: int = 90) -> list[tuple[datetime, float]]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        session.query(MetricObservation.observed_at, MetricObservation.value)
        .filter_by(artist_id=artist_id, source=source, metric=metric)
        .filter(MetricObservation.observed_at >= cutoff)
        .order_by(MetricObservation.observed_at)
        .all()
    )
    return [(r.observed_at, r.value) for r in rows if r.value is not None]


def _latest(session: Session, artist_id, source: str, metric: str) -> Optional[float]:
    row = (
        session.query(MetricObservation.value)
        .filter_by(artist_id=artist_id, source=source, metric=metric)
        .order_by(MetricObservation.observed_at.desc())
        .first()
    )
    return row[0] if row else None


def _mom_growth(series: list[tuple]) -> Optional[float]:
    """Month-over-month growth rate."""
    if len(series) < 2:
        return None
    oldest, newest = series[0][1], series[-1][1]
    if oldest <= 0:
        return None
    return (newest - oldest) / oldest


def _acceleration(series: list[tuple]) -> float:
    """Second derivative: rate of change of growth rate."""
    if len(series) < 3:
        return 0.0
    values = [v for _, v in series]
    x = np.arange(len(values), dtype=float)
    if len(x) < 3:
        return 0.0
    # Fit quadratic, return the coefficient of x^2 (acceleration)
    coeffs = np.polyfit(x, values, 2)
    return float(coeffs[0])


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _sigmoid_score(value: float, midpoint: float, scale: float = 1.0) -> float:
    """Map a raw value to 0-100 via sigmoid centred at midpoint."""
    return 100 / (1 + math.exp(-(value - midpoint) / scale))


# ---------------------------------------------------------------------------
# Individual score computations
# ---------------------------------------------------------------------------

def compute_growth_score(session: Session, artist_id) -> float:
    scores = []

    # Last.fm listeners (primary growth signal)
    lfm = _get_series(session, artist_id, "lastfm", "lfm_listeners", days=90)
    if lfm:
        mom = _mom_growth(lfm) or 0.0
        accel = _acceleration(lfm)
        accel_norm = math.tanh(accel / 1000) * 50   # normalise
        scores.append(_clamp(50 + mom * 200 + accel_norm * 2))   # accel weighted 2×

    # Partyflock fans growth
    pf = _get_series(session, artist_id, "partyflock", "pf_fans", days=90)
    if pf:
        mom = _mom_growth(pf) or 0.0
        scores.append(_clamp(50 + mom * 200))

    return round(float(np.mean(scores)), 2) if scores else 0.0


def compute_momentum_score(session: Session, artist_id) -> float:
    components = []

    # 1. Last.fm listener momentum (MoM)
    lfm = _get_series(session, artist_id, "lastfm", "lfm_listeners", days=90)
    if lfm:
        mom = _mom_growth(lfm) or 0.0
        components.append(("lfm_listeners", _clamp(50 + mom * 150)))

    # 2. RA attending counts (booking heat)
    ra_count = session.query(MetricObservation).filter_by(
        artist_id=artist_id, source="ra", metric="ra_event_attending"
    ).count()
    if ra_count > 0:
        components.append(("ra_events", _clamp(math.log1p(ra_count) * 15)))

    # 3. Partyflock fans (NL demand signal)
    pf_fans = _latest(session, artist_id, "partyflock", "pf_fans")
    if pf_fans is not None:
        components.append(("pf_fans", _clamp(math.log1p(pf_fans) * 8)))

    # 4. Booking frequency (past performances in last 12 months)
    pf_past = _latest(session, artist_id, "partyflock", "pf_past_performances")
    if pf_past is not None:
        components.append(("booking_freq", _clamp(math.log1p(pf_past) * 10)))

    if not components:
        return 0.0

    # Cross-platform resonance: bonus if 3+ sources present
    if len(components) >= 3:
        bonus = 10.0
    else:
        bonus = 0.0

    base = float(np.mean([v for _, v in components]))
    return round(_clamp(base + bonus), 2)


def compute_market_relevance(session: Session, artist_id, framework: SoundFramework) -> float:
    score = 0.0

    # Agency tier (from framework_agency match — requires agency data ingestion)
    # When agency data arrives, lookup artist's agency in framework_agency
    # For now: check validation_event agency_signing
    agency_events = (
        session.query(ValidationEvent)
        .filter_by(artist_id=artist_id, event_type="agency_signing")
        .order_by(ValidationEvent.occurred_at.desc())
        .first()
    )
    if agency_events:
        score += 20.0

    # Framework festival bookings (from lineup_slot → event)
    framework_festival_names = {f.festival_name.lower() for f in framework.festivals}
    festival_slots = (
        session.query(LineupSlot)
        .join(LineupSlot.event)
        .filter(LineupSlot.artist_id == artist_id)
        .all()
    )
    festival_hits = sum(
        1 for s in festival_slots
        if s.event and s.event.name and s.event.name.lower() in framework_festival_names
    )
    score += _clamp(festival_hits * 8, hi=40.0)

    # NL geo presence
    pf_nl_ratio = _latest(session, artist_id, "partyflock", "pf_nl_ratio") or 0.0
    score += pf_nl_ratio * 20.0

    # Geo spread (international reach)
    unique_countries = _latest(session, artist_id, "partyflock", "pf_unique_countries") or 0
    score += _clamp(math.log1p(unique_countries) * 5, hi=20.0)

    return round(_clamp(score), 2)


def compute_future_potential(session: Session, artist_id, framework: SoundFramework) -> float:
    score = 0.0

    # Validation events (recency-weighted)
    val_events = (
        session.query(ValidationEvent)
        .filter_by(artist_id=artist_id)
        .all()
    )
    for ve in val_events:
        age_days = (datetime.utcnow() - ve.occurred_at).days
        recency = math.exp(-age_days / 365)  # decay over ~1 year
        weight = {
            "boiler_room": 15, "ra_podcast": 12, "bbc_r1": 10,
            "ibiza_booking": 10, "circoloco": 10, "music_on": 8,
            "beatport_top10": 8, "beatport_no1": 12,
            "agency_signing": 10,
            "headline_1000": 8, "headline_2000": 12, "headline_5000": 15,
            "tier_a_support": 6, "tier_a_b2b": 5,
        }.get(ve.event_type, 3)
        score += weight * recency

    # Co-appearances with A/A+ benchmark artists
    benchmark_ids = {
        fa.artist_id
        for fa in framework.artists
        if fa.tier in ("A", "A+")
    }
    if benchmark_ids:
        # Events where this artist appeared alongside a benchmark
        artist_event_ids = {
            s.event_id for s in
            session.query(LineupSlot).filter_by(artist_id=artist_id).all()
        }
        for bid in benchmark_ids:
            bench_event_ids = {
                s.event_id for s in
                session.query(LineupSlot).filter_by(artist_id=bid).all()
            }
            co_count = len(artist_event_ids & bench_event_ids)
            if co_count > 0:
                score += min(co_count * 2, 10)

    return round(_clamp(score), 2)


def compute_confidence(session: Session, artist_id) -> float:
    """0-100 representing certainty of scores (data coverage × history length)."""
    source_weights = {"lastfm": 0.35, "partyflock": 0.3, "ra": 0.2, "chartmetric": 0.15}
    coverage_score = 0.0

    for source, weight in source_weights.items():
        has_data = session.query(MetricObservation).filter_by(
            artist_id=artist_id, source=source
        ).first() is not None
        if has_data:
            coverage_score += weight

    # History length bonus
    oldest = (
        session.query(MetricObservation.observed_at)
        .filter_by(artist_id=artist_id)
        .order_by(MetricObservation.observed_at)
        .first()
    )
    if oldest:
        days = (datetime.utcnow() - oldest[0]).days
        history_factor = min(days / MIN_HISTORY_DAYS, 1.0)
    else:
        history_factor = 0.0

    return round(coverage_score * history_factor * 100, 2)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run():
    with get_session() as session:
        framework = session.query(SoundFramework).filter_by(name="tech_house").first()
        if not framework:
            print("No tech_house framework found — run seed_frameworks.py first.")
            return

        artists = session.query(Artist).all()
        print(f"Computing scores for {len(artists)} artists...")
        now = datetime.utcnow()
        computed = 0

        for artist in artists:
            growth = compute_growth_score(session, artist.id)
            momentum = compute_momentum_score(session, artist.id)
            market = compute_market_relevance(session, artist.id, framework)
            future = compute_future_potential(session, artist.id, framework)
            confidence = compute_confidence(session, artist.id)

            for metric, value in [
                ("growth_score", growth),
                ("momentum_score", momentum),
                ("market_relevance", market),
                ("future_potential", future),
                ("confidence_score", confidence),
            ]:
                session.add(MetricObservation(
                    artist_id=artist.id,
                    source="scoring_engine",
                    metric=metric,
                    value=value,
                    observed_at=now,
                ))
            computed += 1

        print(f"Scores written for {computed} artists.")


if __name__ == "__main__":
    run()
