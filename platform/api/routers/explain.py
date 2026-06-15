from datetime import datetime
from uuid import UUID

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import ExplainResponse, ShapFeature
from ml.feature_builder import FeatureBuilder
from ml.train import load_model
from schema.models import Artist

router = APIRouter(prefix="/explain", tags=["explain"])


def _explain_xgb(model_payload: dict, X: np.ndarray, feat_cols: list, proba: np.ndarray, model_name: str) -> list[ShapFeature]:
    """Extract feature contributions via SHAP TreeExplainer."""
    explainer = model_payload.get("explainer")
    if not explainer:
        return []
    shap_vals = explainer.shap_values(X)
    if isinstance(shap_vals, list):
        pred_class = int(np.argmax(proba))
        sv = shap_vals[pred_class][0]
    else:
        sv = shap_vals[0]

    pairs = sorted(zip(feat_cols, X[0], sv), key=lambda t: abs(t[2]), reverse=True)
    return [
        ShapFeature(feature=name, value=round(float(val), 4), shap_value=round(float(s), 4))
        for name, val, s in pairs[:15]
    ]


def _explain_ebm(model_payload: dict, X: np.ndarray, feat_cols: list, proba: np.ndarray) -> list[ShapFeature]:
    """
    Extract feature contributions from EBM's built-in local explanation.
    EBM scores are exact contributions (not approximations like SHAP).
    """
    model = model_payload["model"]
    local_exp = model.explain_local(X)
    d = local_exp.data(0)   # {names, scores, values}

    names = d.get("names", [])
    scores = d.get("scores", [])
    values = d.get("values", [])

    if not names or not scores:
        return []

    pairs = sorted(
        zip(names, values if values else [0.0] * len(names), scores),
        key=lambda t: abs(t[2]),
        reverse=True,
    )
    return [
        ShapFeature(feature=str(name), value=round(float(val), 4), shap_value=round(float(s), 4))
        for name, val, s in pairs[:15]
    ]


@router.get("/{artist_id}", response_model=ExplainResponse)
def explain_artist(
    artist_id: UUID,
    model: str = Query("breakout", description="'breakout' or 'momentum'"),
    model_type: str = Query("ebm", description="'ebm' (primary, glass-box) or 'xgb' (XGBoost+SHAP)"),
    db: Session = Depends(get_db),
):
    if model not in ("breakout", "momentum"):
        raise HTTPException(status_code=422, detail="model must be 'breakout' or 'momentum'")
    if model_type not in ("ebm", "xgb"):
        raise HTTPException(status_code=422, detail="model_type must be 'ebm' or 'xgb'")

    artist = db.query(Artist).filter_by(id=artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    model_name = f"{model}_{model_type}"
    payload = load_model(model_name)
    if not payload:
        raise HTTPException(
            status_code=503,
            detail=f"Model '{model_name}' not trained yet — run python -m ml.train",
        )

    feat_cols = payload["feature_cols"]
    builder = FeatureBuilder(db)
    df = builder.build(as_of=datetime.utcnow())

    row = df[df["artist_id"] == str(artist_id)]
    if row.empty:
        raise HTTPException(status_code=404, detail="No feature data for this artist yet — run ingestion first")

    present = [c for c in feat_cols if c in row.columns]
    X = row[present].fillna(0).values

    mdl = payload["model"]
    proba = mdl.predict_proba(X)[0]
    prediction = float(proba[1]) if model in ("breakout",) else float(proba.max())

    if model_type == "ebm":
        top_features = _explain_ebm(payload, X, present, proba)
    else:
        top_features = _explain_xgb(payload, X, present, proba, model_name)

    return ExplainResponse(
        artist_id=artist_id,
        artist_name=artist.name,
        model=model,
        model_type=model_type,
        prediction=round(prediction, 4),
        top_features=top_features,
        as_of=datetime.utcnow(),
    )
