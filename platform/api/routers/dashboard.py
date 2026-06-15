from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import MomentumDashboard, MoverItem
from schema.models import Artist, MetricObservation

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _score_at(db: Session, artist_id: UUID, metric: str, as_of: datetime) -> float:
    row = (
        db.query(MetricObservation.value)
        .filter(
            MetricObservation.artist_id == artist_id,
            MetricObservation.source == "scoring_engine",
            MetricObservation.metric == metric,
            MetricObservation.observed_at <= as_of,
        )
        .order_by(MetricObservation.observed_at.desc())
        .first()
    )
    return float(row[0]) if row and row[0] is not None else 0.0


@router.get("/momentum", response_model=MomentumDashboard)
def momentum_dashboard(
    db: Session = Depends(get_db),
    top_n: int = 50,
):
    now = datetime.utcnow()
    ago = now - timedelta(days=30)

    artists = db.query(Artist).all()
    movers = []

    for artist in artists:
        g_now = _score_at(db, artist.id, "growth_score", now)
        g_ago = _score_at(db, artist.id, "growth_score", ago)
        m_now = _score_at(db, artist.id, "momentum_score", now)

        delta = g_now - g_ago
        if g_now == 0 and m_now == 0:
            continue

        lofi_row = (
            db.query(MetricObservation.value)
            .filter_by(artist_id=artist.id, source="lofi_internal", metric="lofi_booked")
            .order_by(MetricObservation.observed_at.desc())
            .first()
        )
        lofi_booked = int(lofi_row[0]) if lofi_row and lofi_row[0] is not None else 0

        movers.append(MoverItem(
            id=artist.id,
            name=artist.name,
            growth_score_now=round(g_now, 2),
            growth_score_30d_ago=round(g_ago, 2),
            growth_delta=round(delta, 2),
            momentum_score=round(m_now, 2),
            lofi_booked=lofi_booked,
        ))

    movers.sort(key=lambda x: x.growth_delta, reverse=True)
    return MomentumDashboard(as_of=now, top_movers=movers[:top_n])
