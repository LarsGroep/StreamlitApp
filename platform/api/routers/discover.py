"""
Discover endpoint — surfaces undiscovered artists with LOFI feel.

Returns artists ranked by lofi_similarity that are:
  - Not yet booked by LOFI
  - Below the listener discovery threshold (default 100k Spotify monthly listeners)
  - Optionally filtered by minimum similarity score and growth score

This is the output of ml.similarity.run() — scores must exist in metric_observation
before this endpoint returns meaningful data.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import DiscoverArtist, DiscoverResponse
from schema.models import Artist, MetricObservation

router = APIRouter(prefix="/discover", tags=["discover"])

DEFAULT_LISTENER_THRESHOLD = 100_000


def _latest(db: Session, artist_id: UUID, source: str, metric: str) -> Optional[float]:
    row = (
        db.query(MetricObservation.value)
        .filter_by(artist_id=artist_id, source=source, metric=metric)
        .order_by(MetricObservation.observed_at.desc())
        .first()
    )
    return float(row[0]) if row and row[0] is not None else None


@router.get("/lofi-fit", response_model=DiscoverResponse)
def discover_lofi_fit(
    db: Session = Depends(get_db),
    top_n: int = Query(50, le=200, description="Max results to return"),
    listener_threshold: int = Query(DEFAULT_LISTENER_THRESHOLD, description="Max Spotify monthly listeners"),
    min_similarity: float = Query(0.0, ge=0, le=100, description="Min lofi_similarity score (0-100)"),
    min_growth: float = Query(0.0, ge=0, description="Min growth_score"),
):
    artists = db.query(Artist).all()
    results = []

    for artist in artists:
        # Must have a similarity score
        sim = _latest(db, artist.id, "scoring_engine", "lofi_similarity")
        if sim is None or sim < min_similarity:
            continue

        # Filter: not already LOFI booked
        booked = int(_latest(db, artist.id, "lofi_internal", "lofi_booked") or 0)
        if booked:
            continue

        # Filter: below listener threshold
        listeners = _latest(db, artist.id, "chartmetric", "cm_sp_listeners")
        if listeners is not None and listeners >= listener_threshold:
            continue

        growth = _latest(db, artist.id, "scoring_engine", "growth_score") or 0.0
        if growth < min_growth:
            continue

        momentum = _latest(db, artist.id, "scoring_engine", "momentum_score") or 0.0

        results.append(DiscoverArtist(
            id=artist.id,
            name=artist.name,
            lofi_similarity=round(sim, 1),
            cm_sp_listeners=listeners,
            growth_score=round(growth, 2),
            momentum_score=round(momentum, 2),
        ))

    results.sort(key=lambda x: x.lofi_similarity, reverse=True)

    return DiscoverResponse(
        as_of=datetime.utcnow(),
        listener_threshold=listener_threshold,
        total=len(results),
        artists=results[:top_n],
    )
