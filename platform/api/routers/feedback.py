from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import FeedbackIn, FeedbackResponse
from schema.models import Artist, Feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])

VALID_CATEGORIES = {
    "fits_lofi",
    "doesnt_fit",
    "sound_to_develop",
    "saturated",
    "support_act",
    "potential_headliner",
}


@router.post("/", response_model=FeedbackResponse, status_code=201)
def submit_feedback(payload: FeedbackIn, db: Session = Depends(get_db)):
    artist = db.query(Artist).filter_by(id=payload.artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid category. Must be one of: {sorted(VALID_CATEGORIES)}",
        )

    fb = Feedback(
        id=uuid4(),
        artist_id=payload.artist_id,
        user_id=payload.user_id or "anonymous",
        category=payload.category,
        notes=payload.notes,
        score_delta=payload.score_delta,   # stored as-is, never applied to model output
        created_at=datetime.utcnow(),
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    return FeedbackResponse(id=fb.id, created_at=fb.created_at)
