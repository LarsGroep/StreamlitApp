"""
Phase 5 — Trend radar & anomaly detector.

Two levels:
  1. Artist-level: z-score of each artist's metric vs. their own rolling baseline.
     Flags sudden spikes (growth, fan counts, booking activity).
  2. Market-level: aggregate score trends per genre tag / region.
     Flags emerging or declining genre movements.

Alerts are written to the `alert` table and dispatched via alerts.py.

Usage:
    python -m scoring.anomaly
"""

import math
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from schema.database import get_session
from schema.models import Artist, MetricObservation

# z-score threshold: flag if current value is >N std devs above the artist's own mean
ARTIST_ZSCORE_THRESHOLD = 2.5
# Minimum observations before z-score is meaningful
MIN_OBSERVATIONS = 5
# Rolling baseline window (days)
BASELINE_WINDOW = 90


def _rolling_stats(session: Session, artist_id, source: str, metric: str, as_of: datetime) -> tuple[float, float, float] | None:
    """Returns (mean, std, latest) over the baseline window, or None if insufficient data."""
    cutoff = as_of - timedelta(days=BASELINE_WINDOW)
    rows = (
        session.query(MetricObservation.value, MetricObservation.observed_at)
        .filter(
            MetricObservation.artist_id == artist_id,
            MetricObservation.source == source,
            MetricObservation.metric == metric,
            MetricObservation.observed_at >= cutoff,
            MetricObservation.observed_at <= as_of,
        )
        .order_by(MetricObservation.observed_at)
        .all()
    )
    values = [float(r.value) for r in rows if r.value is not None]
    if len(values) < MIN_OBSERVATIONS:
        return None

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(variance) if variance > 0 else 0.0
    return mean, std, values[-1]


def detect_artist_anomalies(session: Session, as_of: datetime | None = None) -> list[dict]:
    if as_of is None:
        as_of = datetime.utcnow()

    alerts = []
    watch_metrics = [
        ("lastfm",     "lfm_listeners"),
        ("lastfm",     "lfm_playcount"),
        ("partyflock", "pf_fans"),
        ("scoring_engine", "growth_score"),
        ("scoring_engine", "momentum_score"),
    ]

    artists = session.query(Artist).all()
    for artist in artists:
        for source, metric in watch_metrics:
            stats = _rolling_stats(session, artist.id, source, metric, as_of)
            if not stats:
                continue
            mean, std, latest = stats
            if std == 0:
                continue
            z = (latest - mean) / std
            if abs(z) >= ARTIST_ZSCORE_THRESHOLD:
                direction = "spike" if z > 0 else "drop"
                alerts.append({
                    "type":       "artist_anomaly",
                    "artist_id":  str(artist.id),
                    "artist_name": artist.name,
                    "source":     source,
                    "metric":     metric,
                    "z_score":    round(z, 2),
                    "direction":  direction,
                    "latest":     round(latest, 2),
                    "baseline_mean": round(mean, 2),
                    "detected_at": as_of.isoformat(),
                    "message": (
                        f"{'Pay attention to' if direction == 'spike' else 'Check'} "
                        f"{artist.name}: {metric} {direction} "
                        f"(z={z:+.1f}, current={latest:.0f}, avg={mean:.0f})"
                    ),
                })

    return sorted(alerts, key=lambda a: abs(a["z_score"]), reverse=True)


def detect_market_trends(session: Session, as_of: datetime | None = None) -> list[dict]:
    """
    Aggregate growth_score by country (from pf event data) to detect
    regional trends. Placeholder for genre-level trends once tag data
    flows through metric_observation.
    """
    if as_of is None:
        as_of = datetime.utcnow()

    cutoff_30 = as_of - timedelta(days=30)
    cutoff_90 = as_of - timedelta(days=90)

    # Average growth_score per country (via Partyflock event locations)
    # This is a simplified proxy; full genre-level trends need Chartmetric tag data
    from schema.models import Event, LineupSlot

    country_scores_now: dict[str, list[float]] = defaultdict(list)
    country_scores_90:  dict[str, list[float]] = defaultdict(list)

    artists = session.query(Artist).all()
    for artist in artists:
        # Get artist's primary country from most frequent event location
        slots = (
            session.query(LineupSlot)
            .join(LineupSlot.event)
            .filter(LineupSlot.artist_id == artist.id)
            .all()
        )
        countries = [s.event.country for s in slots if s.event and s.event.country]
        if not countries:
            continue
        primary_country = max(set(countries), key=countries.count)

        g_now = (
            session.query(MetricObservation.value)
            .filter(
                MetricObservation.artist_id == artist.id,
                MetricObservation.source == "scoring_engine",
                MetricObservation.metric == "growth_score",
                MetricObservation.observed_at >= cutoff_30,
                MetricObservation.observed_at <= as_of,
            )
            .order_by(MetricObservation.observed_at.desc())
            .first()
        )
        g_90 = (
            session.query(MetricObservation.value)
            .filter(
                MetricObservation.artist_id == artist.id,
                MetricObservation.source == "scoring_engine",
                MetricObservation.metric == "growth_score",
                MetricObservation.observed_at >= cutoff_90,
                MetricObservation.observed_at < cutoff_30,
            )
            .order_by(MetricObservation.observed_at.desc())
            .first()
        )
        if g_now:
            country_scores_now[primary_country].append(float(g_now[0]))
        if g_90:
            country_scores_90[primary_country].append(float(g_90[0]))

    trends = []
    for country in set(country_scores_now) & set(country_scores_90):
        avg_now = sum(country_scores_now[country]) / len(country_scores_now[country])
        avg_90  = sum(country_scores_90[country])  / len(country_scores_90[country])
        delta   = avg_now - avg_90
        if abs(delta) >= 5:
            trends.append({
                "type":      "market_trend",
                "region":    country,
                "avg_growth_now": round(avg_now, 2),
                "avg_growth_90d": round(avg_90, 2),
                "delta":     round(delta, 2),
                "direction": "emerging" if delta > 0 else "declining",
                "n_artists": len(country_scores_now[country]),
                "detected_at": as_of.isoformat(),
                "message": (
                    f"{'Emerging' if delta > 0 else 'Declining'} scene in {country}: "
                    f"avg growth {avg_90:.1f} → {avg_now:.1f} (+{delta:+.1f})"
                ),
            })

    return sorted(trends, key=lambda t: abs(t["delta"]), reverse=True)


def run():
    with get_session() as session:
        now = datetime.utcnow()
        print(f"Running anomaly detection at {now.isoformat()}")

        artist_alerts  = detect_artist_anomalies(session, now)
        market_trends  = detect_market_trends(session, now)

        print(f"Artist anomalies: {len(artist_alerts)}")
        for a in artist_alerts[:10]:
            print(f"  {a['message']}")

        print(f"\nMarket trends: {len(market_trends)}")
        for t in market_trends:
            print(f"  {t['message']}")

        return artist_alerts + market_trends


if __name__ == "__main__":
    run()
