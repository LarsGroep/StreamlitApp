"""
Model training — EBM and XGBoost in parallel for comparison.

Two model heads × two model types = four saved models:
  breakout_ebm.pkl   — P(breakout within 12 months), glass-box EBM
  breakout_xgb.pkl   — same target, XGBoost + SHAP for comparison
  momentum_ebm.pkl   — growing/stable/declining trajectory, glass-box EBM
  momentum_xgb.pkl   — same, XGBoost + SHAP

EBM (ExplainableBoostingClassifier) is the primary model:
  - Inherently interpretable: each feature has a learned response curve
  - Feature contributions via explain_local() — no post-hoc approximation
  - Slightly slower to train but same accuracy class as XGBoost at this data size

XGBoost runs as comparison and SHAP fallback.

Usage:
    python -m ml.train
    python -m ml.train --emerging-only
    python -m ml.train --snapshot 2024-06-01
"""

import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from interpret.glassbox import ExplainableBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit

from ml.feature_builder import FeatureBuilder
from schema.database import get_session

MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

EXCLUDE_COLS = {
    "artist_id", "artist_name", "snapshot_at",
    "lofi_booked", "lofi_appearance_count",
    # scores are outputs, not inputs
    "growth_score", "momentum_score", "market_relevance",
    "future_potential", "confidence_score",
}

BREAKOUT_LABEL = "lofi_booked"
MOMENTUM_LABEL = "momentum_class"


def get_feature_cols(df: pd.DataFrame) -> list[str]:
    return [
        c for c in df.columns
        if c not in EXCLUDE_COLS
        and df[c].dtype in (float, int, np.float64, np.int64)
    ]


def derive_momentum_class(df: pd.DataFrame) -> pd.Series:
    """Map momentum_score → 3-class: 0=declining, 1=stable, 2=growing."""
    s = df["momentum_score"].fillna(50)
    return pd.cut(s, bins=[0, 33, 66, 100], labels=[0, 1, 2], include_lowest=True).astype(int)


# ------------------------------------------------------------------
# XGBoost
# ------------------------------------------------------------------

def _train_xgb_breakout(X: np.ndarray, y: np.ndarray, feat_cols: list) -> dict:
    scale = (y == 0).sum() / max((y == 1).sum(), 1)
    model = xgb.XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=scale, eval_metric="aucpr",
        random_state=42, n_jobs=-1,
    )
    tscv = TimeSeriesSplit(n_splits=3)
    cv_ap, cv_auc = [], []
    for fold, (tr, val) in enumerate(tscv.split(X)):
        if y[val].sum() == 0:
            continue
        model.fit(X[tr], y[tr], eval_set=[(X[val], y[val])], verbose=False)
        proba = model.predict_proba(X[val])[:, 1]
        cv_ap.append(average_precision_score(y[val], proba))
        try:
            cv_auc.append(roc_auc_score(y[val], proba))
        except Exception:
            pass
        print(f"    XGB breakout fold {fold+1}: avg_precision={cv_ap[-1]:.3f}")

    model.fit(X, y, verbose=False)
    explainer = shap.TreeExplainer(model)
    return {
        "model": model, "explainer": explainer, "feature_cols": feat_cols,
        "model_type": "xgb", "head": "breakout",
        "cv_avg_precision": float(np.mean(cv_ap)) if cv_ap else 0.0,
        "cv_auc_roc": float(np.mean(cv_auc)) if cv_auc else 0.0,
        "trained_at": datetime.utcnow().isoformat(),
    }


def _train_xgb_momentum(X: np.ndarray, y: np.ndarray, feat_cols: list) -> dict:
    model = xgb.XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        objective="multi:softprob", num_class=3,
        eval_metric="mlogloss", random_state=42, n_jobs=-1,
    )
    tscv = TimeSeriesSplit(n_splits=3)
    cv_acc = []
    for fold, (tr, val) in enumerate(tscv.split(X)):
        if len(np.unique(y[val])) < 2:
            continue
        model.fit(X[tr], y[tr], eval_set=[(X[val], y[val])], verbose=False)
        acc = model.score(X[val], y[val])
        cv_acc.append(acc)
        print(f"    XGB momentum fold {fold+1}: accuracy={acc:.3f}")

    model.fit(X, y, verbose=False)
    explainer = shap.TreeExplainer(model)
    return {
        "model": model, "explainer": explainer, "feature_cols": feat_cols,
        "model_type": "xgb", "head": "momentum",
        "cv_accuracy": float(np.mean(cv_acc)) if cv_acc else 0.0,
        "trained_at": datetime.utcnow().isoformat(),
    }


# ------------------------------------------------------------------
# EBM
# ------------------------------------------------------------------

def _train_ebm_breakout(X: np.ndarray, y: np.ndarray, feat_cols: list) -> dict:
    model = ExplainableBoostingClassifier(
        feature_names=feat_cols,
        max_bins=256,
        interactions=10,     # pairwise interaction terms (EBM's advantage over linear)
        random_state=42,
        n_jobs=-1,
    )
    tscv = TimeSeriesSplit(n_splits=3)
    cv_ap, cv_auc = [], []
    for fold, (tr, val) in enumerate(tscv.split(X)):
        if y[val].sum() == 0:
            continue
        model.fit(X[tr], y[tr])
        proba = model.predict_proba(X[val])[:, 1]
        cv_ap.append(average_precision_score(y[val], proba))
        try:
            cv_auc.append(roc_auc_score(y[val], proba))
        except Exception:
            pass
        print(f"    EBM breakout fold {fold+1}: avg_precision={cv_ap[-1]:.3f}")

    model.fit(X, y)   # final fit on all data
    return {
        "model": model, "explainer": None, "feature_cols": feat_cols,
        "model_type": "ebm", "head": "breakout",
        "cv_avg_precision": float(np.mean(cv_ap)) if cv_ap else 0.0,
        "cv_auc_roc": float(np.mean(cv_auc)) if cv_auc else 0.0,
        "trained_at": datetime.utcnow().isoformat(),
    }


def _train_ebm_momentum(X: np.ndarray, y: np.ndarray, feat_cols: list) -> dict:
    model = ExplainableBoostingClassifier(
        feature_names=feat_cols,
        max_bins=256,
        interactions=5,
        random_state=42,
        n_jobs=-1,
    )
    tscv = TimeSeriesSplit(n_splits=3)
    cv_acc = []
    for fold, (tr, val) in enumerate(tscv.split(X)):
        if len(np.unique(y[val])) < 2:
            continue
        model.fit(X[tr], y[tr])
        acc = model.score(X[val], y[val])
        cv_acc.append(acc)
        print(f"    EBM momentum fold {fold+1}: accuracy={acc:.3f}")

    model.fit(X, y)
    return {
        "model": model, "explainer": None, "feature_cols": feat_cols,
        "model_type": "ebm", "head": "momentum",
        "cv_accuracy": float(np.mean(cv_acc)) if cv_acc else 0.0,
        "trained_at": datetime.utcnow().isoformat(),
    }


# ------------------------------------------------------------------
# Save / load
# ------------------------------------------------------------------

def save_model(payload: dict):
    name = f"{payload['head']}_{payload['model_type']}"
    path = MODELS_DIR / f"{name}.pkl"
    with path.open("wb") as f:
        pickle.dump(payload, f)
    print(f"  Saved: {path.name}")
    return path


def load_model(name: str) -> Optional[dict]:
    """
    name examples: 'breakout_ebm', 'breakout_xgb', 'momentum_ebm', 'momentum_xgb'
    Also accepts legacy 'breakout' / 'momentum' (defaults to ebm).
    """
    if "_" not in name:
        name = f"{name}_ebm"
    path = MODELS_DIR / f"{name}.pkl"
    if not path.exists():
        return None
    with path.open("rb") as f:
        return pickle.load(f)


# ------------------------------------------------------------------
# Comparison report
# ------------------------------------------------------------------

def _print_comparison(breakout_ebm: dict, breakout_xgb: dict, momentum_ebm: dict, momentum_xgb: dict):
    sep = "─" * 52
    print(f"\n{'═'*52}")
    print(f"  Model Comparison Report")
    print(f"{'═'*52}")
    print(f"\n  Breakout model (P(breakout within 12 months))")
    print(sep)
    for p in [breakout_ebm, breakout_xgb]:
        print(f"  {p['model_type'].upper():<6}  avg_precision={p['cv_avg_precision']:.3f}  "
              f"AUC-ROC={p['cv_auc_roc']:.3f}")
    winner_b = "EBM" if breakout_ebm["cv_avg_precision"] >= breakout_xgb["cv_avg_precision"] else "XGBoost"
    print(f"  → Primary: {winner_b}")

    print(f"\n  Momentum model (growing / stable / declining)")
    print(sep)
    for p in [momentum_ebm, momentum_xgb]:
        print(f"  {p['model_type'].upper():<6}  accuracy={p.get('cv_accuracy', 0):.3f}")
    winner_m = "EBM" if momentum_ebm.get("cv_accuracy", 0) >= momentum_xgb.get("cv_accuracy", 0) else "XGBoost"
    print(f"  → Primary: {winner_m}")
    print(f"{'═'*52}\n")

    # Save report as JSON
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "breakout": {
            "ebm": {"avg_precision": breakout_ebm["cv_avg_precision"], "auc_roc": breakout_ebm["cv_auc_roc"]},
            "xgb": {"avg_precision": breakout_xgb["cv_avg_precision"], "auc_roc": breakout_xgb["cv_auc_roc"]},
            "primary": winner_b.lower(),
        },
        "momentum": {
            "ebm": {"accuracy": momentum_ebm.get("cv_accuracy", 0)},
            "xgb": {"accuracy": momentum_xgb.get("cv_accuracy", 0)},
            "primary": winner_m.lower(),
        },
    }
    report_path = MODELS_DIR / "comparison_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"  Report saved to {report_path.name}")


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

@click.command()
@click.option("--emerging-only", is_flag=True, default=False, help="Train breakout models only")
@click.option("--established-only", is_flag=True, default=False, help="Train momentum models only")
@click.option("--snapshot", default=None, help="Point-in-time snapshot (YYYY-MM-DD)")
def main(emerging_only: bool, established_only: bool, snapshot: Optional[str]):
    as_of = datetime.fromisoformat(snapshot) if snapshot else datetime.utcnow()

    with get_session() as session:
        print(f"Building feature matrix as of {as_of.date()}...")
        builder = FeatureBuilder(session)
        df = builder.build(as_of=as_of)

    if df.empty:
        print("No data — run seed_artists + ingestion first.")
        return

    print(f"Feature matrix: {df.shape[0]} artists × {df.shape[1]} columns")
    print(f"  LOFI-booked (positive label): {df[BREAKOUT_LABEL].sum()}")

    feat_cols = get_feature_cols(df)
    X_all = df[feat_cols].fillna(0).values

    be_payload = bx_payload = me_payload = mx_payload = None

    if not established_only:
        y_b = df[BREAKOUT_LABEL].fillna(0).values.astype(int)
        if y_b.sum() < 10:
            print(f"  Warning: only {y_b.sum()} positive labels — collect more history before trusting predictions.")

        print("\nTraining breakout models...")
        print("  [EBM]")
        be_payload = _train_ebm_breakout(X_all, y_b, feat_cols)
        save_model(be_payload)

        print("  [XGBoost]")
        bx_payload = _train_xgb_breakout(X_all, y_b, feat_cols)
        save_model(bx_payload)

    if not emerging_only:
        df_m = df.copy()
        df_m[MOMENTUM_LABEL] = derive_momentum_class(df_m)
        y_m = df_m[MOMENTUM_LABEL].values

        print("\nTraining momentum models...")
        print("  [EBM]")
        me_payload = _train_ebm_momentum(X_all, y_m, feat_cols)
        save_model(me_payload)

        print("  [XGBoost]")
        mx_payload = _train_xgb_momentum(X_all, y_m, feat_cols)
        save_model(mx_payload)

    if be_payload and bx_payload and me_payload and mx_payload:
        _print_comparison(be_payload, bx_payload, me_payload, mx_payload)

    print("Done. Run `python -m ml.backtest` to evaluate on historical snapshots.")


if __name__ == "__main__":
    main()
