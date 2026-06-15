from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import ArtistProfile, ArtistSearchResult, ArtistSummary, ScoreSnapshot, ValidationEventOut, FeedbackOut
from schema.models import Artist, Feedback, MetricObservation, ValidationEvent

router = APIRouter(prefix="/artists", tags=["artists"])


def _latest_metric(db: Session, artist_id: UUID, source: str, metric: str) -> Optional[float]:
    row = (
        db.query(MetricObservation.value)
        .filter_by(artist_id=artist_id, source=source, metric=metric)
        .order_by(MetricObservation.observed_at.desc())
        .first()
    )
    return float(row[0]) if row and row[0] is not None else None


def _build_scores(db: Session, artist_id: UUID) -> Optional[ScoreSnapshot]:
    metrics = {}
    for m in ("growth_score", "momentum_score", "market_relevance", "future_potential", "confidence_score"):
        row = (
            db.query(MetricObservation)
            .filter_by(artist_id=artist_id, source="scoring_engine", metric=m)
            .order_by(MetricObservation.observed_at.desc())
            .first()
        )
        if row:
            metrics[m] = (row.value, row.observed_at)

    if not metrics:
        return None

    latest_at = max(v[1] for v in metrics.values())
    return ScoreSnapshot(
        growth_score=     metrics.get("growth_score",     (0.0,))[0],
        momentum_score=   metrics.get("momentum_score",   (0.0,))[0],
        market_relevance= metrics.get("market_relevance", (0.0,))[0],
        future_potential= metrics.get("future_potential", (0.0,))[0],
        confidence_score= metrics.get("confidence_score", (0.0,))[0],
        computed_at=latest_at,
    )


@router.get("/{artist_id}", response_model=ArtistProfile)
def get_artist(artist_id: UUID, db: Session = Depends(get_db)):
    artist = db.query(Artist).filter_by(id=artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    val_events = [
        ValidationEventOut(
            event_type=ve.event_type,
            occurred_at=ve.occurred_at,
            source=ve.source or "auto",
            notes=ve.notes,
        )
        for ve in db.query(ValidationEvent)
        .filter_by(artist_id=artist_id)
        .order_by(ValidationEvent.occurred_at.desc())
        .all()
    ]

    feedbacks = [
        FeedbackOut(
            id=fb.id,
            category=fb.category or "",
            notes=fb.notes,
            score_delta=fb.score_delta,
            created_at=fb.created_at,
        )
        for fb in db.query(Feedback)
        .filter_by(artist_id=artist_id)
        .order_by(Feedback.created_at.desc())
        .all()
    ]

    return ArtistProfile(
        id=artist.id,
        name=artist.name,
        scores=_build_scores(db, artist_id),
        lofi_booked=int(_latest_metric(db, artist_id, "lofi_internal", "lofi_booked") or 0),
        lofi_appearances=int(_latest_metric(db, artist_id, "lofi_internal", "lofi_appearance_count") or 0),
        lofi_similarity=_latest_metric(db, artist_id, "scoring_engine", "lofi_similarity"),
        cm_sp_listeners=_latest_metric(db, artist_id, "chartmetric", "cm_sp_listeners"),
        pf_fans=_latest_metric(db, artist_id, "partyflock", "pf_fans"),
        pf_past_perfs=_latest_metric(db, artist_id, "partyflock", "pf_past_performances"),
        lfm_listeners=_latest_metric(db, artist_id, "lastfm", "lfm_listeners"),
        lfm_growth_90d=_latest_metric(db, artist_id, "lastfm", "lfm_growth_90d"),
        validation_events=val_events,
        feedback=feedbacks,
    )


@router.get("/", response_model=ArtistSearchResult)
def search_artists(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Name search"),
    lofi_booked: Optional[int] = Query(None, description="1=booked only, 0=not booked"),
    min_growth: Optional[float] = Query(None, description="Min growth_score"),
    max_growth: Optional[float] = Query(None, description="Max growth_score"),
    min_momentum: Optional[float] = Query(None, description="Min momentum_score"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    artists = db.query(Artist).all()

    results = []
    for artist in artists:
        scores = _build_scores(db, artist.id)
        g_score = scores.growth_score   if scores else 0.0
        m_score = scores.momentum_score if scores else 0.0

        if min_growth   is not None and g_score < min_growth:   continue
        if max_growth   is not None and g_score > max_growth:   continue
        if min_momentum is not None and m_score < min_momentum: continue

        booked = int(_latest_metric(db, artist.id, "lofi_internal", "lofi_booked") or 0)
        if lofi_booked is not None and booked != lofi_booked:
            continue

        if q and q.lower() not in artist.name.lower():
            continue

        results.append(ArtistSummary(
            id=artist.id,
            name=artist.name,
            growth_score=g_score,
            momentum_score=m_score,
            lofi_booked=booked,
            lfm_listeners=_latest_metric(db, artist.id, "lastfm", "lfm_listeners"),
            pf_fans=_latest_metric(db, artist.id, "partyflock", "pf_fans"),
        ))

    results.sort(key=lambda x: x.growth_score, reverse=True)
    total = len(results)
    return ArtistSearchResult(total=total, artists=results[offset: offset + limit])
