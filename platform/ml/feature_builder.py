"""
Point-in-time feature builder for ML training and inference.

Builds a feature vector for each artist as of a given snapshot_date, using
ONLY data observable at that date (no leakage). Queries metric_observation
hypertable directly — no flat files.

Usage:
    # Current snapshot (inference)
    builder = FeatureBuilder(session)
    df = builder.build(as_of=datetime.utcnow())

    # Historical snapshot (training)
    df = builder.build(as_of=datetime(2024, 6, 1))
    df.to_csv("snapshots/2024-06-01.csv", index=False)
"""

import math
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from schema.models import (
    Artist, ArtistSourceMap, LineupSlot, MetricObservation,
    SoundFramework, ValidationEvent,
)

# Rolling windows (days)
SHORT_WINDOW = 30
LONG_WINDOW  = 90

TECHNO_TAGS = {
    "techno", "tech house", "tech-house", "dark techno", "hard techno",
    "industrial techno", "minimal techno", "acid techno", "dub techno",
    "deep tech", "electro", "house", "deep house", "progressive house",
    "minimal", "ambient techno",
}

YEARS = [2021, 2022, 2023, 2024, 2025]


class FeatureBuilder:
    def __init__(self, session: Session):
        self.session = session
        self._framework: Optional[SoundFramework] = None

    @property
    def framework(self):
        if self._framework is None:
            self._framework = (
                self.session.query(SoundFramework)
                .filter_by(name="tech_house")
                .first()
            )
        return self._framework

    # ------------------------------------------------------------------
    # Core query helpers — all respect the as_of date
    # ------------------------------------------------------------------

    def _latest(self, artist_id, source: str, metric: str, as_of: datetime) -> Optional[float]:
        row = (
            self.session.query(MetricObservation.value)
            .filter(
                MetricObservation.artist_id == artist_id,
                MetricObservation.source == source,
                MetricObservation.metric == metric,
                MetricObservation.observed_at <= as_of,
            )
            .order_by(MetricObservation.observed_at.desc())
            .first()
        )
        return float(row[0]) if row and row[0] is not None else None

    def _series(self, artist_id, source: str, metric: str, as_of: datetime, days: int) -> list[float]:
        cutoff = as_of - timedelta(days=days)
        rows = (
            self.session.query(MetricObservation.value)
            .filter(
                MetricObservation.artist_id == artist_id,
                MetricObservation.source == source,
                MetricObservation.metric == metric,
                MetricObservation.observed_at > cutoff,
                MetricObservation.observed_at <= as_of,
            )
            .order_by(MetricObservation.observed_at)
            .all()
        )
        return [float(r[0]) for r in rows if r[0] is not None]

    def _growth_rate(self, series: list[float]) -> float:
        if len(series) < 2 or series[0] <= 0:
            return 0.0
        return (series[-1] - series[0]) / series[0]

    def _acceleration(self, series: list[float]) -> float:
        """Second derivative — rate of change of the growth rate."""
        if len(series) < 3:
            return 0.0
        x = np.arange(len(series), dtype=float)
        coeffs = np.polyfit(x, series, 2)
        return float(coeffs[0])  # quadratic coefficient = acceleration

    # ------------------------------------------------------------------
    # Feature groups
    # ------------------------------------------------------------------

    def _lfm_features(self, artist_id, as_of: datetime) -> dict:
        listeners_30 = self._series(artist_id, "lastfm", "lfm_listeners", as_of, SHORT_WINDOW)
        listeners_90 = self._series(artist_id, "lastfm", "lfm_listeners", as_of, LONG_WINDOW)
        latest_listeners = listeners_90[-1] if listeners_90 else 0.0
        latest_playcount = self._latest(artist_id, "lastfm", "lfm_playcount", as_of) or 0.0
        tag_count        = self._latest(artist_id, "lastfm", "lfm_tag_count", as_of) or 0.0
        similar_count    = self._latest(artist_id, "lastfm", "lfm_similar_count", as_of) or 0.0

        # Tags snapshot — needed for has_techno_tag
        tag_row = (
            self.session.query(MetricObservation)
            .filter(
                MetricObservation.artist_id == artist_id,
                MetricObservation.source == "lastfm",
                MetricObservation.metric == "lfm_tag_count",
                MetricObservation.observed_at <= as_of,
            )
            .order_by(MetricObservation.observed_at.desc())
            .first()
        )

        growth_30 = self._growth_rate(listeners_30)
        growth_90 = self._growth_rate(listeners_90)
        accel     = self._acceleration(listeners_90)

        return {
            "lfm_listeners":          latest_listeners,
            "lfm_playcount":          latest_playcount,
            "lfm_log_listeners":      round(math.log1p(latest_listeners), 4),
            "lfm_log_playcount":      round(math.log1p(latest_playcount), 4),
            "lfm_plays_per_listener": round(latest_playcount / latest_listeners, 4) if latest_listeners > 0 else 0.0,
            "lfm_tag_count":          tag_count,
            "lfm_similar_count":      similar_count,
            "lfm_growth_30d":         round(growth_30, 4),
            "lfm_growth_90d":         round(growth_90, 4),
            "lfm_acceleration":       round(accel, 6),
        }

    def _pf_artist_features(self, artist_id, as_of: datetime) -> dict:
        fans     = self._latest(artist_id, "partyflock", "pf_fans", as_of) or 0.0
        past     = self._latest(artist_id, "partyflock", "pf_past_performances", as_of) or 0.0
        upcoming = self._latest(artist_id, "partyflock", "pf_upcoming_performances", as_of) or 0.0
        vote     = self._latest(artist_id, "partyflock", "pf_vote_score", as_of) or 0.0

        fans_30 = self._series(artist_id, "partyflock", "pf_fans", as_of, SHORT_WINDOW)
        fans_90 = self._series(artist_id, "partyflock", "pf_fans", as_of, LONG_WINDOW)

        return {
            "pf_fans":             fans,
            "pf_log_fans":         round(math.log1p(fans), 4),
            "pf_past_perfs":       past,
            "pf_log_past":         round(math.log1p(past), 4),
            "pf_upcoming_perfs":   upcoming,
            "pf_vote_score":       vote,
            "pf_fans_growth_30d":  round(self._growth_rate(fans_30), 4),
            "pf_fans_growth_90d":  round(self._growth_rate(fans_90), 4),
        }

    def _pf_event_features(self, artist_id, as_of: datetime) -> dict:
        cutoff = as_of - timedelta(days=5 * 365)
        slots = (
            self.session.query(LineupSlot)
            .join(LineupSlot.event)
            .filter(
                LineupSlot.artist_id == artist_id,
                LineupSlot.event.has(date=None) == False,
            )
            .all()
        )
        events = [s.event for s in slots if s.event and s.event.date and s.event.date <= as_of and s.event.date >= cutoff]

        countries = [e.country for e in events if e.country]
        cities    = [e.city for e in events if e.city]
        total     = len(events)

        nl_count  = sum(1 for c in countries if c == "NL")
        nl_ratio  = round(nl_count / total, 3) if total > 0 else 0.0
        unique_c  = len(set(countries))
        unique_ci = len(set(cities))
        geo_spread = round(unique_c / total, 4) if total > 0 else 0.0

        from collections import Counter
        year_counts = Counter(e.date.year for e in events if e.date)
        yr_vals = [int(year_counts.get(y, 0)) for y in YEARS]

        slope = 0.0
        if sum(yr_vals) > 0:
            x = np.array(YEARS, dtype=float)
            y = np.array(yr_vals, dtype=float)
            xc = x - x.mean()
            denom = np.dot(xc, xc)
            slope = float(np.dot(xc, y) / denom) if denom != 0 else 0.0

        feat = {
            "pf_total_events":      total,
            "pf_unique_countries":  unique_c,
            "pf_unique_cities":     unique_ci,
            "pf_nl_ratio":          nl_ratio,
            "pf_geo_spread":        geo_spread,
            "pf_events_trend_slope": round(slope, 4),
            "pf_log_total_events":  round(math.log1p(total), 4),
        }
        for yr, val in zip(YEARS, yr_vals):
            feat[f"pf_events_{yr}"] = val
        return feat

    def _ra_features(self, artist_id, as_of: datetime) -> dict:
        slots = (
            self.session.query(LineupSlot)
            .join(LineupSlot.event)
            .filter(
                LineupSlot.artist_id == artist_id,
                LineupSlot.event.has(source="ra"),
            )
            .all()
        )
        events = [s.event for s in slots if s.event and (s.event.date is None or s.event.date <= as_of)]
        cities = [e.city for e in events if e.city]
        return {
            "ra_upcoming_events": len(events),
            "ra_unique_cities":   len(set(cities)),
        }

    def _validation_features(self, artist_id, as_of: datetime) -> dict:
        events = (
            self.session.query(ValidationEvent)
            .filter(
                ValidationEvent.artist_id == artist_id,
                ValidationEvent.occurred_at <= as_of,
            )
            .all()
        )
        counts = {
            "val_ibiza":         sum(1 for e in events if e.event_type == "ibiza_booking"),
            "val_boiler_room":   sum(1 for e in events if e.event_type == "boiler_room"),
            "val_ra_podcast":    sum(1 for e in events if e.event_type == "ra_podcast"),
            "val_beatport_top10":sum(1 for e in events if e.event_type == "beatport_top10"),
            "val_agency_signed": int(any(e.event_type == "agency_signing" for e in events)),
            "val_headline_1000": int(any(e.event_type in ("headline_1000", "headline_2000", "headline_5000") for e in events)),
            "val_total":         len(events),
        }
        return counts

    def _score_features(self, artist_id, as_of: datetime) -> dict:
        scores = {}
        for metric in ("growth_score", "momentum_score", "market_relevance", "future_potential", "confidence_score"):
            val = self._latest(artist_id, "scoring_engine", metric, as_of)
            scores[metric] = val if val is not None else 0.0
        return scores

    def _lofi_features(self, artist_id, as_of: datetime) -> dict:
        booked = self._latest(artist_id, "lofi_internal", "lofi_booked", as_of)
        count  = self._latest(artist_id, "lofi_internal", "lofi_appearance_count", as_of)
        return {
            "lofi_booked":            int(booked) if booked is not None else 0,
            "lofi_appearance_count":  int(count)  if count  is not None else 0,
        }

    # ------------------------------------------------------------------
    # Main build
    # ------------------------------------------------------------------

    def build(self, as_of: Optional[datetime] = None) -> pd.DataFrame:
        if as_of is None:
            as_of = datetime.utcnow()

        artists = self.session.query(Artist).all()
        rows = []

        for artist in artists:
            lfm  = self._lfm_features(artist.id, as_of)

            # Skip if no data at all at this snapshot date
            if lfm["lfm_listeners"] == 0 and lfm["lfm_playcount"] == 0:
                pf = self._pf_artist_features(artist.id, as_of)
                if pf["pf_fans"] == 0 and pf["pf_past_perfs"] == 0:
                    continue
            else:
                pf = self._pf_artist_features(artist.id, as_of)

            # Skip mainstream artists (>1.5M listeners)
            if lfm["lfm_listeners"] > 1_500_000:
                continue

            row = {
                "artist_id":   str(artist.id),
                "artist_name": artist.name,
                "snapshot_at": as_of.isoformat(),
            }
            row.update(lfm)
            row.update(pf)
            row.update(self._pf_event_features(artist.id, as_of))
            row.update(self._ra_features(artist.id, as_of))
            row.update(self._validation_features(artist.id, as_of))
            row.update(self._score_features(artist.id, as_of))
            row.update(self._lofi_features(artist.id, as_of))
            rows.append(row)

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        num_cols = df.select_dtypes(include="number").columns
        df[num_cols] = df[num_cols].fillna(0)
        return df


if __name__ == "__main__":
    from schema.database import get_session
    with get_session() as session:
        builder = FeatureBuilder(session)
        df = builder.build()
        print(f"Feature matrix: {df.shape[0]} artists × {df.shape[1]} columns")
        out = __import__("pathlib").Path(__file__).parent.parent / "data" / "features_current.csv"
        out.parent.mkdir(exist_ok=True)
        df.to_csv(out, index=False)
        print(f"Saved to {out}")
