from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Artist
# ---------------------------------------------------------------------------

class ScoreSnapshot(BaseModel):
    growth_score:      float
    momentum_score:    float
    market_relevance:  float
    future_potential:  float
    confidence_score:  float
    computed_at:       datetime


class ValidationEventOut(BaseModel):
    event_type:  str
    occurred_at: datetime
    source:      str
    notes:       Optional[str] = None


class FeedbackOut(BaseModel):
    id:          UUID
    category:    str
    notes:       Optional[str] = None
    score_delta: Optional[dict] = None
    created_at:  datetime


class ArtistProfile(BaseModel):
    id:           UUID
    name:         str
    scores:       Optional[ScoreSnapshot] = None
    lofi_booked:  int
    lofi_appearances: int
    lofi_similarity: Optional[float] = None   # 0-100, cosine similarity to LOFI-booked centroid
    cm_sp_listeners: Optional[float] = None
    pf_fans:      Optional[float] = None
    pf_past_perfs: Optional[float] = None
    lfm_listeners: Optional[float] = None
    lfm_growth_90d: Optional[float] = None
    validation_events: list[ValidationEventOut] = []
    feedback:     list[FeedbackOut] = []


class ArtistSummary(BaseModel):
    id:            UUID
    name:          str
    growth_score:  float
    momentum_score: float
    lofi_booked:   int
    lfm_listeners: Optional[float] = None
    pf_fans:       Optional[float] = None


class ArtistSearchResult(BaseModel):
    total:   int
    artists: list[ArtistSummary]


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class MoverItem(BaseModel):
    id:              UUID
    name:            str
    growth_score_now:  float
    growth_score_30d_ago: float
    growth_delta:    float
    momentum_score:  float
    lofi_booked:     int


class MomentumDashboard(BaseModel):
    as_of:    datetime
    top_movers: list[MoverItem]


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class FeedbackIn(BaseModel):
    artist_id:   UUID
    user_id:     Optional[str] = "anonymous"
    category:    str   # fits_lofi | doesnt_fit | sound_to_develop | saturated | support_act | potential_headliner
    notes:       Optional[str] = None
    score_delta: Optional[dict] = None  # e.g. {"momentum_score": 5, "future_potential": -10}


class FeedbackResponse(BaseModel):
    id:         UUID
    created_at: datetime


# ---------------------------------------------------------------------------
# Explain
# ---------------------------------------------------------------------------

class ShapFeature(BaseModel):
    feature:    str
    value:      float
    shap_value: float


class ExplainResponse(BaseModel):
    artist_id:     UUID
    artist_name:   str
    model:         str        # "breakout" | "momentum"
    model_type:    str        # "ebm" (glass-box) | "xgb" (XGBoost + SHAP)
    prediction:    float
    top_features:  list[ShapFeature]
    as_of:         datetime


# ---------------------------------------------------------------------------
# Discover
# ---------------------------------------------------------------------------

class DiscoverArtist(BaseModel):
    id:              UUID
    name:            str
    lofi_similarity: float      # 0-100
    cm_sp_listeners: Optional[float] = None
    growth_score:    float
    momentum_score:  float


class DiscoverResponse(BaseModel):
    as_of:               datetime
    listener_threshold:  int
    total:               int
    artists:             list[DiscoverArtist]
