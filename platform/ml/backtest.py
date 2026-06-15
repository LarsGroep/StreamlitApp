"""
Backtester — evaluates model hit rate on held-out historical cohorts.

Strategy: walk-forward test using multiple historical snapshots.
For each snapshot date S:
  - Build features as_of S
  - Predict breakout probability
  - Check what actually happened in the following 12 months
    (lofi_booked events, validation events)
  - Report precision/recall by score percentile

Usage:
    python -m ml.backtest
    python -m ml.backtest --report docs/backtest_report.md
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import click
import numpy as np
import pandas as pd
import shap
from sklearn.calibration import calibration_curve
from sklearn.metrics import average_precision_score, precision_recall_curve

from schema.database import get_session
from ml.feature_builder import FeatureBuilder
from ml.train import load_model, get_feature_cols

DOCS_DIR = Path(__file__).parent.parent / "docs"

# Snapshot dates for walk-forward evaluation
# As data accumulates, add more dates here
SNAPSHOT_DATES = [
    datetime(2024, 1,  1),
    datetime(2024, 6,  1),
    datetime(2024, 12, 1),
    datetime(2025, 6,  1),
]
OUTCOME_WINDOW_DAYS = 365


def evaluate_cohort(
    session,
    model_payload: dict,
    snapshot_date: datetime,
    outcome_date: datetime,
) -> dict | None:
    builder = FeatureBuilder(session)
    df_snap = builder.build(as_of=snapshot_date)
    if df_snap.empty:
        return None

    df_outcome = builder.build(as_of=outcome_date)
    if df_outcome.empty:
        return None

    feat_cols = model_payload["feature_cols"]
    model     = model_payload["model"]
    present   = [c for c in feat_cols if c in df_snap.columns]
    if not present:
        return None

    X = df_snap[present].fillna(0).values
    proba = model.predict_proba(X)[:, 1]

    # Ground truth: did lofi_booked change from 0→1 in the outcome window?
    snap_ids = set(df_snap["artist_id"])
    out_map  = df_outcome.set_index("artist_id")["lofi_booked"].to_dict()
    snap_map = df_snap.set_index("artist_id")["lofi_booked"].to_dict()

    labels = np.array([
        int(out_map.get(aid, 0) > snap_map.get(aid, 0))
        for aid in df_snap["artist_id"]
    ])

    if labels.sum() == 0:
        return {"snapshot": snapshot_date.date().isoformat(), "note": "no new breakouts in window"}

    ap = average_precision_score(labels, proba)
    precision, recall, thresholds = precision_recall_curve(labels, proba)

    # Hit rate at top-20% threshold
    cutoff = np.percentile(proba, 80)
    top20_mask = proba >= cutoff
    hit_rate = labels[top20_mask].mean() if top20_mask.sum() > 0 else 0.0

    # Calibration
    frac_pos, mean_pred = calibration_curve(labels, proba, n_bins=5)

    return {
        "snapshot":     snapshot_date.date().isoformat(),
        "outcome_by":   outcome_date.date().isoformat(),
        "n_artists":    len(df_snap),
        "n_breakouts":  int(labels.sum()),
        "avg_precision": round(float(ap), 3),
        "hit_rate_top20pct": round(float(hit_rate), 3),
        "calibration": {
            "fraction_positives": [round(float(x), 3) for x in frac_pos],
            "mean_predicted":     [round(float(x), 3) for x in mean_pred],
        },
    }


def build_report(results: list[dict], model_meta: dict) -> str:
    lines = [
        "# Backtest Report",
        f"\nGenerated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
        f"Model trained: {model_meta.get('trained_at', 'unknown')}",
        f"CV score (avg_precision): {model_meta.get('cv_score', 'n/a')}",
        "\n## Walk-forward Cohort Results\n",
        "| Snapshot | Outcome By | Artists | Breakouts | Avg Precision | Hit Rate Top-20% |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        if "note" in r:
            lines.append(f"| {r['snapshot']} | — | — | — | — | {r['note']} |")
        else:
            lines.append(
                f"| {r['snapshot']} | {r['outcome_by']} | {r['n_artists']} | "
                f"{r['n_breakouts']} | {r['avg_precision']} | {r['hit_rate_top20pct']} |"
            )

    lines += [
        "\n## Interpretation",
        "",
        "- **Avg Precision**: area under precision-recall curve. Random baseline = breakout base rate.",
        "- **Hit Rate Top-20%**: of artists in the top-20% by predicted score, fraction that actually broke out.",
        "- **Target** (from route map): hit rate of 65–75% as data matures.",
        "",
        "## Notes",
        "",
        "- Walk-forward evaluation uses only data observable at snapshot time (no leakage).",
        "- 'Breakout' defined as `lofi_booked` transitioning 0→1 in the 12-month outcome window.",
        "- Model reliability improves as `metric_observation` history accumulates (target: 60+ days per artist, 3+ sources).",
        "- Rerun quarterly: `python -m ml.backtest`",
    ]
    return "\n".join(lines)


@click.command()
@click.option("--report", default=str(DOCS_DIR / "backtest_report.md"), help="Output report path")
def main(report: str):
    model_payload = load_model("breakout")
    if not model_payload:
        print("No trained model found — run `python -m ml.train` first.")
        return

    results = []
    with get_session() as session:
        for snap_date in SNAPSHOT_DATES:
            outcome_date = snap_date + timedelta(days=OUTCOME_WINDOW_DAYS)
            if outcome_date > datetime.utcnow():
                print(f"Skipping {snap_date.date()} — outcome window extends into the future")
                continue
            print(f"Evaluating cohort: snapshot={snap_date.date()} outcome_by={outcome_date.date()}")
            result = evaluate_cohort(session, model_payload, snap_date, outcome_date)
            if result:
                results.append(result)
                print(f"  → avg_precision={result.get('avg_precision', 'n/a')} hit_rate={result.get('hit_rate_top20pct', 'n/a')}")

    if not results:
        print("No completed cohorts yet — need historical data spanning at least one full outcome window.")
        md = build_report([], model_payload)
    else:
        md = build_report(results, model_payload)

    out = Path(report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"\nReport saved: {out}")


if __name__ == "__main__":
    main()
