"""
LOFI Feel Similarity System.

Computes how closely each artist's profile matches the "LOFI sound" by comparing
their feature vector against the centroid of the 755 known LOFI-booked artists.

Discovery target: artists below 100k Spotify monthly listeners.
This is the Tier B / pre-Tier-B range — where the next Chris Stussy, Josh Baker
or Kolter will be found 6-18 months before the wider market sees them.

Outputs:
  - lofi_similarity score (0-100) written to metric_observation for all artists
  - CLI report: top undiscovered artists ranked by similarity

Usage:
    python -m ml.similarity
    python -m ml.similarity --top-n 30 --threshold 75000
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

import click
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from schema.database import get_session
from schema.models import Artist, MetricObservation

log = logging.getLogger(__name__)

# Artists above this are already on the market's radar — not the discovery target.
# Aligns with Tier B benchmark artists (Toman, Julian Fijma, Luuk van Dijk, etc.)
DEFAULT_LISTENER_THRESHOLD = 100_000

# Feature set: Chartmetric primary, supplemented by Last.fm + Partyflock + heuristic scores.
# Intentionally excludes raw size metrics (cm_sp_listeners) from the similarity computation
# so that listener count doesn't dominate — we want sound/scene fit, not popularity.
SIMILARITY_FEATURES = [
    # Spotify profile shape
    "cm_sp_popularity",          # 0-100 Spotify popularity index
    "cm_sp_editorial_count",     # editorial playlist presence = taste-maker signal
    "cm_sp_playlist_reach",      # total playlist follower reach
    # Beatport presence (electronic scene credibility)
    "cm_beatport_inv_rank",      # 1/rank so higher = better; 0 if no chart entry
    # Geographic profile — NL/EU concentration matters for LOFI audience fit
    "cm_geo_nl_share",
    "cm_geo_eu_share",
    # Cross-platform presence (electronic artists have SoundCloud + IG presence)
    "cm_soundcloud_followers",
    "cm_instagram_followers",
    # Scene credibility from Last.fm
    "lfm_listeners",
    "lfm_playcount",
    "lfm_tag_count",             # genre tag breadth
    "lfm_similar_count",         # similar artist network density
    # Partyflock — NL/EU live presence
    "pf_fans",
    "pf_past_performances",
    # Heuristic scores from scoring engine
    "market_relevance",          # framework ecosystem activity
    "future_potential",          # agency tier + validation events
]


# ------------------------------------------------------------------
# Feature extraction
# ------------------------------------------------------------------

def _latest(session, artist_id: UUID, source: str, metric: str) -> Optional[float]:
    row = (
        session.query(MetricObservation.value)
        .filter_by(artist_id=artist_id, source=source, metric=metric)
        .order_by(MetricObservation.observed_at.desc())
        .first()
    )
    return float(row[0]) if row and row[0] is not None else None


_SOURCE_MAP = {
    "cm_sp_popularity":        ("chartmetric", "cm_sp_popularity"),
    "cm_sp_editorial_count":   ("chartmetric", "cm_sp_editorial_count"),
    "cm_sp_playlist_reach":    ("chartmetric", "cm_sp_playlist_reach"),
    "cm_beatport_inv_rank":    ("chartmetric", "cm_beatport_inv_rank"),
    "cm_geo_nl_share":         ("chartmetric", "cm_geo_nl_share"),
    "cm_geo_eu_share":         ("chartmetric", "cm_geo_eu_share"),
    "cm_soundcloud_followers": ("chartmetric", "cm_soundcloud_followers"),
    "cm_instagram_followers":  ("chartmetric", "cm_instagram_followers"),
    "lfm_listeners":           ("lastfm",      "lfm_listeners"),
    "lfm_playcount":           ("lastfm",      "lfm_playcount"),
    "lfm_tag_count":           ("lastfm",      "lfm_tag_count"),
    "lfm_similar_count":       ("lastfm",      "lfm_similar_count"),
    "pf_fans":                 ("partyflock",  "pf_fans"),
    "pf_past_performances":    ("partyflock",  "pf_past_performances"),
    "market_relevance":        ("scoring_engine", "market_relevance"),
    "future_potential":        ("scoring_engine", "future_potential"),
}


def _build_row(session, artist: Artist) -> dict:
    row: dict = {"artist_id": str(artist.id), "artist_name": artist.name}

    for feat, (source, metric) in _SOURCE_MAP.items():
        row[feat] = _latest(session, artist.id, source, metric)

    # Size metrics (used for filtering, not similarity)
    row["cm_sp_listeners"] = _latest(session, artist.id, "chartmetric", "cm_sp_listeners")
    row["lofi_booked"] = int(_latest(session, artist.id, "lofi_internal", "lofi_booked") or 0)
    row["growth_score"] = _latest(session, artist.id, "scoring_engine", "growth_score")
    row["momentum_score"] = _latest(session, artist.id, "scoring_engine", "momentum_score")
    return row


def build_matrix(session) -> pd.DataFrame:
    artists = session.query(Artist).all()
    rows = [_build_row(session, a) for a in artists]
    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# Similarity computation
# ------------------------------------------------------------------

def compute_similarity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute cosine similarity of every artist to the LOFI-booked centroid.
    Returns df with 'lofi_similarity' column (0-100).
    """
    feat_cols = [c for c in SIMILARITY_FEATURES if c in df.columns]
    X = df[feat_cols].fillna(0).values.astype(float)

    # StandardScaler: removes scale dominance (listeners vs. share fractions)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    lofi_mask = df["lofi_booked"].fillna(0) == 1
    n_lofi = lofi_mask.sum()
    if n_lofi < 5:
        raise ValueError(f"Only {n_lofi} LOFI-booked artists — need ≥5 for centroid. Run seed_artists first.")

    centroid = X_scaled[lofi_mask].mean(axis=0, keepdims=True)
    log.info("LOFI centroid computed from %d artists", n_lofi)

    sims = cosine_similarity(X_scaled, centroid).flatten()
    # Cosine similarity is [-1, 1]; clip to [0, 1] then scale to 0-100
    df = df.copy()
    df["lofi_similarity"] = np.round(np.clip(sims, 0, 1) * 100, 1)
    return df


# ------------------------------------------------------------------
# Discovery output
# ------------------------------------------------------------------

def find_undiscovered(df: pd.DataFrame, listener_threshold: int, top_n: int) -> pd.DataFrame:
    """
    Artists with LOFI-fit but below the listener threshold — the discovery target.
    Not already booked by LOFI, growing, and culturally adjacent to the LOFI cluster.
    """
    mask = (
        (df["lofi_booked"].fillna(0) == 0) &
        (df["cm_sp_listeners"].fillna(0) < listener_threshold)
    )
    return (
        df[mask]
        .nlargest(top_n, "lofi_similarity")
        [["artist_id", "artist_name", "lofi_similarity", "cm_sp_listeners",
          "growth_score", "momentum_score"]]
        .reset_index(drop=True)
    )


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def run(top_n: int = 50, threshold: int = DEFAULT_LISTENER_THRESHOLD):
    """Run similarity computation and write scores — callable from orchestrator."""
    with get_session() as session:
        print("Building feature matrix...")
        df = build_matrix(session)
        print(f"  {len(df)} artists, {df['lofi_booked'].sum()} LOFI-booked")

        try:
            df = compute_similarity(df)
        except ValueError as e:
            print(f"Cannot compute similarity: {e}")
            return

        now = datetime.utcnow()
        written = 0
        for _, row in df.iterrows():
            if pd.isna(row["lofi_similarity"]):
                continue
            session.add(MetricObservation(
                artist_id=row["artist_id"],
                source="scoring_engine",
                metric="lofi_similarity",
                value=float(row["lofi_similarity"]),
                observed_at=now,
            ))
            written += 1
        print(f"Wrote {written} lofi_similarity scores to metric_observation")

        undiscovered = find_undiscovered(df, threshold, top_n)
        print(f"\n{'═'*60}")
        print(f"  Top {top_n} undiscovered LOFI-fit artists  (<{threshold:,} Spotify listeners)")
        print(f"{'═'*60}")
        for i, r in undiscovered.iterrows():
            listeners = f"{int(r['cm_sp_listeners']):,}" if not pd.isna(r.get("cm_sp_listeners", float("nan"))) else "?"
            growth = f"  growth={r['growth_score']:.0f}" if not pd.isna(r.get("growth_score", float("nan"))) else ""
            print(f"  {i+1:2d}. [{r['lofi_similarity']:.0f}] {r['artist_name']:<30} {listeners} listeners{growth}")


@click.command()
@click.option("--top-n", default=50, type=int)
@click.option("--threshold", default=DEFAULT_LISTENER_THRESHOLD, type=int)
def main(top_n: int, threshold: int):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(top_n=top_n, threshold=threshold)


if __name__ == "__main__":
    main()
