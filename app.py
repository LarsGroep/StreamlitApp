import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error
from skrub import TableVectorizer
from pathlib import Path
from collections import defaultdict
import shap

ARCHIVE_DIR = Path(__file__).parent / "archive"

st.set_page_config(page_title="Demo Weight Slider XGBoost predictor op meerdere datasets", layout="wide")

st.markdown("""
<style>
    section[data-testid="stSidebar"] { display: none; }
    button[data-testid="collapsedControl"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("XAI type shit")

csv_files = sorted(f.name for f in ARCHIVE_DIR.glob("*.csv"))
if not csv_files:
    st.error(f"No CSV files found in {ARCHIVE_DIR}")
    st.stop()

cfg1, cfg2, cfg3 = st.columns(3)

with cfg1:
    selected_file = st.selectbox("Dataset", csv_files)


@st.cache_data
def load_raw(fname: str) -> pd.DataFrame:
    return pd.read_csv(ARCHIVE_DIR / fname)


df_raw = load_raw(selected_file)

# Only numeric columns are valid regression targets
numeric_target_cols = df_raw.select_dtypes(include=[np.number]).columns.tolist()
if not numeric_target_cols:
    st.error("Geen kolommen met nummers.")
    st.stop()

DEFAULT_TARGETS = {"song_popularity", "ranking"}
default_target  = next((c for c in numeric_target_cols if c in DEFAULT_TARGETS),
                       numeric_target_cols[0])

with cfg2:
    target_col = st.selectbox("Target (what to predict)", numeric_target_cols,
                               index=numeric_target_cols.index(default_target))

with cfg3:
    n_top = st.slider("Auto-select top N features", min_value=3, max_value=30,
                      value=10, step=1)

st.caption(f"{len(df_raw):,} rows · {len(df_raw.columns)} cols")

@st.cache_resource
def vectorize_and_rank(fname: str, target: str):
    """
    skrub
    """
    df = pd.read_csv(ARCHIVE_DIR / fname)
    df = df.dropna(subset=[target]).reset_index(drop=True)

    y = pd.to_numeric(df[target], errors="coerce").values.astype(np.float32)
    valid = ~np.isnan(y)
    df, y = df[valid].reset_index(drop=True), y[valid]

    features_df = df.drop(columns=[target])

    
    JUNK_KEYWORDS = {"url", "uri", "href", "link", "id", "uuid",
                     "lyrics", "text", "description", "html", "type"}

    def is_junk(col: str, series: pd.Series) -> bool:
        if any(kw in col.lower() for kw in JUNK_KEYWORDS):
            return True
        # Drop string columns where almost every value is unique (IDs, free text)
        if series.dtype == object:
            n_unique = series.nunique(dropna=True)
            n_total  = series.notna().sum()
            if n_total > 0 and n_unique / n_total > 0.9:
                return True
        return False

    usable_cols = [c for c in features_df.columns
                   if not is_junk(c, features_df[c])]
    features_df = features_df[usable_cols]

    if features_df.empty:
        return None, None, None, None, "No usable feature columns after filtering."

    tv = TableVectorizer()
    try:
        X_full = tv.fit_transform(features_df).to_numpy().astype(np.float32)
    except Exception as e:
        return None, None, None, None, str(e)

    transformed_names = tv.get_feature_names_out()

    
    quick = XGBRegressor(n_estimators=100, max_depth=4, random_state=42, verbosity=0)
    quick.fit(X_full, y)

   
    orig_imp: dict[str, float] = defaultdict(float)
    for fname_t, imp in zip(transformed_names, quick.feature_importances_):
        orig_col = fname_t.split("__")[0]   # skrub uses col__value for encoded cols
        orig_imp[orig_col] += float(imp)

    ranked_cols = sorted(orig_imp, key=orig_imp.__getitem__, reverse=True)
    ranked_scores = [orig_imp[c] for c in ranked_cols]

    return tv, features_df, y, ranked_cols, ranked_scores


tv, features_df, y, ranked_cols, ranked_scores = vectorize_and_rank(
    selected_file, target_col
)

if tv is None:
    st.error(f"Preprocessing failed: {ranked_cols}")
    st.stop()


auto_selected = ranked_cols[:n_top]

with st.expander("Edit selected features", expanded=False):
    user_selected = st.multiselect(
        "Features (ranked by model importance)",
        options=ranked_cols,
        default=auto_selected,
        key=f"feat_sel_{selected_file}_{target_col}"
    )

if not user_selected:
    st.warning("Select at least one feature.")
    st.stop()

# ── Step 3: fit final model on selected features ──────────────────────────────
@st.cache_resource
def fit_final(fname: str, target: str, selected: tuple):
    df = pd.read_csv(ARCHIVE_DIR / fname)
    df = df.dropna(subset=[target]).reset_index(drop=True)
    y  = pd.to_numeric(df[target], errors="coerce").values.astype(np.float32)
    valid = ~np.isnan(y)
    df, y = df[valid].reset_index(drop=True), y[valid]

    sub_df = df[[c for c in selected if c in df.columns]]
    tv2    = TableVectorizer()
    X      = tv2.fit_transform(sub_df).to_numpy().astype(np.float32)
    feat_names = list(tv2.get_feature_names_out())

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
    model = XGBRegressor(n_estimators=300, max_depth=5, learning_rate=0.05,
                         subsample=0.8, colsample_bytree=0.8,
                         random_state=42, verbosity=0)
    model.fit(X_tr, y_tr)

    r2   = float(r2_score(y_te, model.predict(X_te)))
    rmse = float(np.sqrt(mean_squared_error(y_te, model.predict(X_te))))

    np.random.seed(42)
    idx    = np.random.choice(len(X), min(500, len(X)), replace=False)
    X_samp = X[idx]
    y_samp = y[idx]

    explainer  = shap.TreeExplainer(model)
    shap_vals  = explainer.shap_values(X_samp)
    base_value = float(explainer.expected_value)

    label_col = next(
        (c for c in ["song", "song_name", "band_singer", "title", "name"] if c in df.columns),
        None
    )
    labels = df[label_col].values[idx] if label_col else np.array([f"row {i}" for i in idx])

    return (model, X_samp, y_samp, shap_vals, base_value,
            r2, rmse, feat_names, labels, int(len(y)))


(model, X_samp, y_samp, shap_vals, base_value,
 r2, rmse, feat_names, hover_labels, n_rows) = fit_final(
    selected_file, target_col, tuple(user_selected)
)

# ── Slider state ──────────────────────────────────────────────────────────────
state_key = f"sl_{selected_file}_{target_col}_{'_'.join(user_selected)}"
for f in feat_names:
    if f"w_{state_key}_{f}" not in st.session_state:
        st.session_state[f"w_{state_key}_{f}"] = 1.0

multipliers = np.array(
    [st.session_state[f"w_{state_key}_{f}"] for f in feat_names],
    dtype=np.float32
)

# ── Apply multipliers ─────────────────────────────────────────────────────────
adj_importance = np.abs(shap_vals).mean(axis=0) * multipliers
y_pred         = model.predict(X_samp * multipliers)

st.caption(
    f"**{selected_file}** · predicting `{target_col}` · "
    f"top {len(user_selected)} features (auto-selected by XGBoost importance) · "
    f"{n_rows:,} rows"
)

m1, m2, m3 = st.columns(3)
m1.metric("R² (test set)",   f"{r2:.3f}")
m2.metric("RMSE (test set)", f"{rmse:.2f}")
m3.metric("Rows used",       f"{n_rows:,}")

# Show feature ranking from the importance pass
with st.expander("Feature ranking (all columns, auto-scored)"):
    rank_df = pd.DataFrame({
        "Original column": ranked_cols,
        "Importance score": [f"{s:.4f}" for s in ranked_scores],
        "Selected": ["✓" if c in user_selected else "" for c in ranked_cols]
    })
    st.dataframe(rank_df, use_container_width=True, hide_index=True)

st.divider()

# ── Plots ─────────────────────────────────────────────────────────────────────
col_scatter, col_shap = st.columns([2, 1])

with col_scatter:
    lo = float(min(y_samp.min(), y_pred.min()))
    hi = float(max(y_samp.max(), y_pred.max()))
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=y_samp, y=y_pred, mode="markers",
        text=hover_labels,
        marker=dict(size=5, color="#1f77b4", opacity=0.5),
        name="Samples",
        hovertemplate="<b>%{text}</b><br>Actual: %{x:.1f}<br>Predicted: %{y:.1f}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=[lo, hi], y=[lo, hi], mode="lines",
        line=dict(dash="dash", color="red", width=2),
        name="Perfect prediction"
    ))
    fig.update_layout(
        title=f"Actual vs. Predicted · `{target_col}`",
        xaxis_title=f"Actual {target_col}",
        yaxis_title=f"Predicted {target_col}",
        hovermode="closest", height=420
    )
    st.plotly_chart(fig, use_container_width=True)

with col_shap:
    order      = np.argsort(adj_importance)
    feat_order = [feat_names[i] for i in order]
    imp_order  = adj_importance[order]
    mean_dir   = shap_vals.mean(axis=0)
    colors     = ["#2ca02c" if mean_dir[i] >= 0 else "#d62728" for i in order]

    fig_shap = go.Figure(go.Bar(
        x=imp_order, y=feat_order, orientation="h", marker_color=colors
    ))
    fig_shap.update_layout(
        title="SHAP Feature Importance",
        xaxis_title="Mean |SHAP value|",
        height=420
    )
    st.plotly_chart(fig_shap, use_container_width=True)

# ── Per-sample explanation ────────────────────────────────────────────────────
with st.expander("Explain a specific sample"):
    idx_pick = st.slider("Sample index", 0, len(y_samp) - 1, 0)
    sv       = shap_vals[idx_pick] * multipliers
    s_order  = np.argsort(np.abs(sv))
    fig_exp  = go.Figure(go.Bar(
        x=[float(sv[i]) for i in s_order],
        y=[feat_names[i] for i in s_order],
        orientation="h",
        marker_color=["#2ca02c" if sv[i] >= 0 else "#d62728" for i in s_order]
    ))
    fig_exp.update_layout(
        title=(
            f"{hover_labels[idx_pick]}  ·  "
            f"baseline {base_value:.1f} → predicted {float(y_pred[idx_pick]):.1f} "
            f"| actual {float(y_samp[idx_pick]):.1f}"
        ),
        xaxis_title="SHAP value",
        height=350
    )
    st.plotly_chart(fig_exp, use_container_width=True)

st.divider()

# ── Human-in-the-loop sliders ─────────────────────────────────────────────────
st.subheader("Human-in-the-Loop: Adjust Feature Importance")
st.caption("1.0 = model default · 0.0 = ignore this feature · 2.0 = double its influence")

n_cols  = min(4, len(feat_names))
sl_cols = st.columns(n_cols)
for i, feat in enumerate(feat_names):
    with sl_cols[i % n_cols]:
        st.slider(feat, min_value=0.0, max_value=3.0, step=0.1,
                  key=f"w_{state_key}_{feat}")

def _reset_weights(keys: list[str]) -> None:
    for k in keys:
        st.session_state[k] = 1.0

st.button(
    "Reset all weights",
    type="secondary",
    on_click=_reset_weights,
    args=([f"w_{state_key}_{feat}" for feat in feat_names],),
)

changed = [f"**{f}** ×{v:.1f}" for f, v in zip(feat_names, multipliers) if v != 1.0]
if changed:
    st.info("Active adjustments: " + " · ".join(changed))
else:
    st.info("All features at model default — predictions driven purely by data.")
