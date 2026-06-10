"""
Armadillo @ Lofi — Pipeline Demo
Single-page Streamlit app styled as a Word document.
"""

import json

import itertools

import sys

from collections import Counter, defaultdict

from pathlib import Path

import altair as alt

import numpy as np

import pandas as pd

import plotly.express as px

import plotly.graph_objects as go

import shap

import streamlit as st

from sklearn.metrics import mean_squared_error, r2_score

from sklearn.model_selection import train_test_split

from skrub import TableVectorizer

from xgboost import XGBRegressor

BASE = Path(__file__).parent

ARCHIVE_DIR = BASE / "archive"

TIMESERIES_DIR = BASE / "TimeseriesCMtest-main"

RA_DIR = BASE / "ra-scraper-master" / "scraper"

CHARTMETRIC_DIR = BASE / "Chartmetric Genre Data"

BILLBOARD_CSV = ARCHIVE_DIR / "billboard_24years_lyrics_spotify.csv"

ENERGY_TARGET = "energy"

LOFI_NORMALIZED_CSV = TIMESERIES_DIR / "artist_metrics_normalized.csv"

LEN_FAKI_RAW_DIR = TIMESERIES_DIR / "chartmetric_len_faki_history_raw"

st.set_page_config(

    page_title="Armadillo @ Lofi — Pipeline Demo",

    layout="wide",

    initial_sidebar_state="collapsed",

)

st.markdown("""
<style>
/* ── hide sidebar completely ── */
section[data-testid="stSidebar"],
button[data-testid="collapsedControl"] { display: none !important; }

/* ── dark page background ── */
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stMain"] { background: #0d0d0f !important; }

/* ── dark content container, full wide ── */
.block-container,
.stMainBlockContainer {
    max-width: 1400px !important;
    background: #13131a !important;
    padding: 48px 64px 80px 64px !important;
}

/* ── top bar ── */
[data-testid="stHeader"] { background: #0d0d0f !important; border-bottom: 1px solid #1e1e2e !important; }

/* ── body text ── */
p, li, div, span,
.stMarkdown p, .stMarkdown li {
    font-family: 'Segoe UI', 'Inter', 'Calibri', sans-serif !important;
    font-size: 12.5pt !important;
    line-height: 1.8 !important;
    color: #c8c8d8 !important;
}

/* ── headings ── */
h1 {
    font-family: 'Segoe UI', 'Inter', 'Calibri', sans-serif !important;
    font-size: 52pt !important;
    font-weight: 700 !important;
    color: #e8e8f0 !important;
    border-bottom: 3px solid #3a6bc4 !important;
    padding-bottom: 10px !important;
    margin-bottom: 4px !important;
    letter-spacing: -0.5px !important;
}

h2 {
    font-family: 'Segoe UI', 'Inter', 'Calibri', sans-serif !important;
    font-size: 20pt !important;
    font-weight: 700 !important;
    color: #dde4f5 !important;
    border-bottom: 1px solid #2a2a3e !important;
    padding-bottom: 6px !important;
    margin-top: 48px !important;
    margin-bottom: 16px !important;
}

h3 {
    font-family: 'Segoe UI', 'Inter', 'Calibri', sans-serif !important;
    font-size: 15pt !important;
    font-weight: 600 !important;
    color: #8ab4f8 !important;
    margin-top: 28px !important;
    margin-bottom: 10px !important;
}

h4 {
    font-family: 'Segoe UI', 'Inter', 'Calibri', sans-serif !important;
    font-size: 13pt !important;
    color: #a0b4cc !important;
    margin-top: 18px !important;
}

/* ── TOC box ── */
.toc-box {
    background: #1a1a2e;
    border-left: 4px solid #3a6bc4;
    padding: 18px 26px 14px 26px;
    margin: 18px 0 28px 0;
    font-family: 'Segoe UI', 'Calibri', sans-serif;
    font-size: 10.5pt;
    line-height: 2.1;
}
.toc-box a { color: #8ab4f8 !important; text-decoration: none; }
.toc-box a:hover { text-decoration: underline; color: #aac8ff !important; }

/* ── info callout ── */
.callout {
    background: #141d2e;
    border-left: 4px solid #3a6bc4;
    padding: 12px 18px;
    margin: 14px 0;
    font-family: 'Segoe UI', 'Calibri', sans-serif;
    font-size: 10pt;
    border-radius: 0 3px 3px 0;
    color: #c8c8d8 !important;
}
.callout-amber {
    background: #1e1a10;
    border-left-color: #d4870a;
}
.callout-green {
    background: #101e16;
    border-left-color: #2ecc71;
}

/* ── coming-soon badge ── */
.badge-wip {
    display: inline-block;
    background: #2a2a3e;
    color: #8898bb !important;
    font-family: 'Segoe UI', 'Calibri', sans-serif;
    font-size: 8.5pt;
    padding: 2px 9px;
    border-radius: 3px;
    margin-left: 8px;
    vertical-align: middle;
    letter-spacing: 0.05em;
    border: 1px solid #3a3a58;
}

/* ── figure caption ── */
.fig-cap {
    text-align: center;
    font-style: italic;
    font-size: 9pt;
    color: #5a6a88;
    margin-top: -4px;
    margin-bottom: 18px;
    font-family: 'Segoe UI', 'Calibri', sans-serif;
}

/* ── metric cards ── */
[data-testid="stMetric"] {
    background: #1a1a28 !important;
    border: 1px solid #252538 !important;
    border-top: 3px solid #3a6bc4 !important;
    padding: 12px 16px !important;
    border-radius: 3px !important;
}
[data-testid="stMetricLabel"] > div {
    font-family: 'Segoe UI', 'Calibri', sans-serif !important;
    font-size: 11pt !important;
    color: #7080a0 !important;
}
[data-testid="stMetricValue"] > div {
    font-family: 'Segoe UI', 'Calibri', sans-serif !important;
    font-size: 22pt !important;
    color: #8ab4f8 !important;
}

/* ── dataframes ── */
[data-testid="stDataFrame"] { border: 1px solid #252538 !important; }

/* ── selectbox ── */
[data-baseweb="select"] > div {
    background: #1a1a28 !important;
    border-radius: 3px !important;
    border-color: #2e2e48 !important;
    color: #c8c8d8 !important;
}
[data-baseweb="popover"],
[data-baseweb="option"] { background: #1e1e30 !important; color: #c8c8d8 !important; }

/* ── sliders ── */
[data-testid="stSlider"] label {
    font-family: 'Segoe UI', 'Calibri', sans-serif !important;
    font-size: 9.5pt !important;
    color: #a0aec0 !important;
}
[data-baseweb="slider"] [role="slider"] { background: #3a6bc4 !important; }

/* ── tabs ── */
[data-baseweb="tab-list"] { background: #1a1a28 !important; border-bottom: 1px solid #252538 !important; }
[data-baseweb="tab"] { color: #7080a0 !important; }
[aria-selected="true"][data-baseweb="tab"] { color: #8ab4f8 !important; border-bottom: 2px solid #3a6bc4 !important; }

hr { border-color: #1e1e2e !important; margin: 32px 0 !important; }

/* ── caption (st.caption) ── */
[data-testid="stCaptionContainer"] p { color: #556080 !important; font-size: 9pt !important; }

.event-row {
    border-left: 3px solid #3a6bc4;
    padding: 6px 12px;
    margin: 4px 0;
    background: #1a1a28;
    font-family: 'Segoe UI', 'Calibri', sans-serif;
    font-size: 9.5pt;
}
.event-future { border-left-color: #2ecc71; background: #101e16; }
</style>
""", unsafe_allow_html=True)

                                                                                

          

                                                                                

def fig_layout(height=400):

    return dict(

        paper_bgcolor="rgba(0,0,0,0)",

        plot_bgcolor="#1a1a28",

        font=dict(family="Segoe UI, Calibri, sans-serif", color="#c8c8d8", size=13),

        margin=dict(l=8, r=8, t=40, b=8),

        height=height,

    )

AXIS = dict(gridcolor="#252538", linecolor="#252538", tickcolor="#404060", zerolinecolor="#252538")

                                                                                

                

                                                                                

st.markdown("# Armadillo @ lofi")

st.markdown("**Pipeline demo · 10 juni 2026**")

st.markdown(

    '<p style="color:#e8e8f0;font-size:11pt;margin-top:-6px;">'

    "We hebben dit weekend en tot gister vooral research gedaan naar gerelateerde werken "

    "op Kaggle en Github samen met het zoeken naar datasets die gaan lijken op onze chartmetric dataset."

    "</p>",

    unsafe_allow_html=True,

)

_c1, _c2, _c3 = st.columns([2, 3, 2])

with _c2:

    st.image(str(BASE / "ArmadilloBijLofi.jpeg"), use_container_width=True)

st.markdown("""
We hebben meerdere datasets gebruikt voor het maken van een concept van een eindproduct.
Deze pagina is een opsomming van de componenten die we tot nu toe werkend hebben en
hoe we de componenten willen gebruiken in ons eindproduct.
""")

                                                                                 

st.markdown("## Inhoud")

st.markdown("""
<div class="toc-box">
<b>1.</b> &nbsp;<a href="#chartmetric-data-analyse">Chartmetric Data analyse</a> — welke data werken we mee<br>
<b>2.</b> &nbsp;<a href="#ai-component-xgboost">AI Component (XGBoost)</a> — voorspelmodel met feature-importance sliders<br>
<b>3.</b> &nbsp;<a href="#resident-advisor-scraper">Resident Advisor Scraper</a> — concertprofielen en lineup-combinaties<br>
<b>4.</b> &nbsp;<a href="#reddit-scraper">Reddit Scraper</a> <span class="badge-wip">Work in progress</span><br>
<b>5.</b> &nbsp;<a href="#llm-assistent">LLM Assistent</a> <span class="badge-wip">Coming soon</span>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

                                                                                

                      

                                                                                

st.markdown('<a name="chartmetric-data-analyse"></a>', unsafe_allow_html=True)

st.markdown("## 1. Chartmetric Data analyse")

st.markdown("""
Hoe ziet de data eruit: we hebben alle artiesten in de Lofi Airtable naast Chartmetric data gelegd
om te kijken hoe Chartmetric deze artiesten labelt op het gebied van genre. Daarna hebben we een
API-request gedaan voor de **top 10.000 House artiesten** op Chartmetric, samen met zoveel
mogelijk data per artiest.
""")

st.markdown("""
<div class="callout callout-amber">
⚠️ &nbsp;<b>Let op:</b> Dit zijn de top 10.000 artiesten uit de brede House-categorie op Chartmetric —
dit is nog <b>niet gepersonaliseerd</b> voor Lofi. De volgende stap is betere filtering op basis van
de Lofi Airtable data, zodat de dataset aansluit op jullie specifieke booking-stijl en artiest-profiel.
</div>
""", unsafe_allow_html=True)

@st.cache_data

def load_chartmetric_df():

    return pd.read_csv(CHARTMETRIC_DIR / "techno_artists.csv")

cm_df = load_chartmetric_df()

st.markdown("### Dataset overzicht")

st.dataframe(cm_df.head(8), use_container_width=True, hide_index=True)

st.markdown('<p class="fig-cap">Tabel 1 — Eerste 8 rijen uit de Chartmetric dataset (top 10.000 House artiesten, selectie kolommen).</p>', unsafe_allow_html=True)

                                                                               

if "genres" in cm_df.columns:

    all_genres = (

        cm_df["genres"]

        .dropna()

        .str.split(",")

        .explode()

        .str.strip()

        .value_counts()

        .head(20)

        .reset_index()

    )

    all_genres.columns = ["genre", "count"]

    fig_g = go.Figure(go.Bar(

        x=all_genres["count"],

        y=all_genres["genre"],

        orientation="h",

        marker_color="#3a6bc4",

        marker_opacity=0.85,

    ))

    fig_g.update_layout(

        **fig_layout(380),

        title="Top 20 genres — Chartmetric dataset",

        xaxis_title="Aantal artiesten",

        yaxis=dict(autorange="reversed", tickfont=dict(size=10), **AXIS),

        xaxis=dict(**AXIS),

    )

    st.plotly_chart(fig_g, use_container_width=True, config=dict(displayModeBar=False))

    st.markdown('<p class="fig-cap">Figuur 1 — Genreverdeling van de top 10.000 House artiesten op Chartmetric.</p>', unsafe_allow_html=True)

st.markdown("### Len Faki — tijdreeks per platform")

st.markdown("""
Als demo kijken we naar één artiest in detail: **Len Faki**. De Chartmetric API geeft tijdreeksen
terug van Spotify-volgers, luisteraars, Instagram-engagement en een eigen career-score. Dit zijn
precies de features die we straks gebruiken in het XGBoost-model om een *rise to fame* te voorspellen.
""")

@st.cache_data

def load_len_faki_metrics():

    if LOFI_NORMALIZED_CSV.exists():

        try:

            df = pd.read_csv(LOFI_NORMALIZED_CSV, parse_dates=["date"], keep_default_na=False)

            return df

        except Exception:

            pass

    return pd.DataFrame()

lf_df = load_len_faki_metrics()

METRIC_LABELS = {

    "followers": "Spotify Volgers",

    "listeners": "Spotify Luisteraars",

    "instagram_followers": "Instagram Volgers",

    "instagram_engagement_rate": "Instagram Engagement Rate",

    "career_stage": "Career Stage Score",

    "career_momentum": "Career Momentum Score",

    "artist_rank": "Artiest Rank (Chartmetric)",

}

if lf_df.empty:

    st.markdown('<div class="callout callout-amber">⚠️ Geen genormaliseerde tijdreeksdata gevonden voor Len Faki.</div>', unsafe_allow_html=True)

else:

    artist_df = lf_df[lf_df["artist_name"] == "Len Faki"].copy()

    def latest(metric):

        q = artist_df[artist_df["metric"] == metric].dropna(subset=["date"])

        if q.empty:

            return None

        return q.sort_values("date").iloc[-1]["value_numeric"]

    m_sp_f = latest("followers")

    m_sp_l = latest("listeners")

    m_ig_f = latest("instagram_followers")

    m_rank = latest("artist_rank")

    c1, c2, c3, c4 = st.columns(4)

    for col, label, val in [

        (c1, "Spotify Volgers", m_sp_f),

        (c2, "Spotify Luisteraars", m_sp_l),

        (c3, "Instagram Volgers", m_ig_f),

        (c4, "Artiest Rank", m_rank),

    ]:

        if val is not None and not np.isnan(val):

            col.metric(label, f"{int(val):,}")

        else:

            col.metric(label, "—")

    available_metrics = [

        k for k in METRIC_LABELS

        if not artist_df[artist_df["metric"] == k].empty

    ]

    if available_metrics:

        chosen_key = st.selectbox(

            "Kies metric voor tijdreeks",

            options=available_metrics,

            format_func=lambda k: METRIC_LABELS[k],

            key="lf_metric_sel",

        )

        chart_df = (

            artist_df[artist_df["metric"] == chosen_key]

            .dropna(subset=["date", "value_numeric"])

            .sort_values("date")

        )

        if not chart_df.empty:

            fig_lf = go.Figure()

            fig_lf.add_trace(go.Scatter(

                x=chart_df["date"],

                y=chart_df["value_numeric"],

                mode="lines+markers",

                line=dict(color="#8ab4f8", width=2),

                marker=dict(size=5, color="#8ab4f8"),

                name=METRIC_LABELS[chosen_key],

            ))

            fig_lf.update_layout(

                **fig_layout(320),

                title=f"Len Faki — {METRIC_LABELS[chosen_key]}",

                xaxis_title="Datum",

                yaxis_title=METRIC_LABELS[chosen_key],

                xaxis=dict(**AXIS),

                yaxis=dict(**AXIS),

            )

            st.plotly_chart(fig_lf, use_container_width=True, config=dict(displayModeBar=False))

            st.markdown('<p class="fig-cap">Figuur 2 — Tijdreeks van Len Faki vanuit Chartmetric API.</p>', unsafe_allow_html=True)

st.markdown("""
<div class="callout">
<b>Toelichting:</b> Bovenstaande features (Spotify-volgers, luisteraars, Instagram-engagement,
career-score, artiest-rank) zijn de input voor ons XGBoost-model. Het uiteindelijke doel is het
<b>voorspellen van een toekomstige 'rise to fame'</b> van een artiest — zodat Lofi vroeg kan
boeken en een lagere fee betaalt.
</div>
""", unsafe_allow_html=True)

st.markdown("---")

                                                                                

                            

                                                                                

st.markdown('<a name="ai-component-xgboost"></a>', unsafe_allow_html=True)

st.markdown("## 2. AI Component — XGBoost")

st.markdown("""
We gebruiken een **XGBoost regressiemodel** om te kijken of je met de beschikbare features
andere features kunt voorspellen. De data lijkt sterk op de Chartmetric artiest-data qua structuur.
Als demo gebruiken we de **Billboard 24-jaar dataset** met Spotify audio-features en
voorspellen we het `energy`-label — dit is een goed proxy om te laten zien hoe het model werkt.
""")

BILL_FEATURES = [

    "danceability", "key", "loudness", "mode", "speechiness",

    "acousticness", "instrumentalness", "liveness", "valence",

    "tempo", "duration_ms", "time_signature", "year", "ranking",

]

@st.cache_resource

def train_xgboost_model():

    df = pd.read_csv(BILLBOARD_CSV)

    df = df.dropna(subset=[ENERGY_TARGET]).reset_index(drop=True)

    feat_cols = [c for c in BILL_FEATURES if c in df.columns]

    X = df[feat_cols].fillna(df[feat_cols].median())

    y = df[ENERGY_TARGET].values.astype(np.float32)

    X_tr, X_te, y_tr, y_te = train_test_split(X.values, y, test_size=0.2, random_state=42)

    model = XGBRegressor(

        n_estimators=300, max_depth=5, learning_rate=0.05,

        subsample=0.8, colsample_bytree=0.8,

        random_state=42, verbosity=0,

    )

    model.fit(X_tr, y_tr)

    r2 = float(r2_score(y_te, model.predict(X_te)))

    rmse = float(np.sqrt(mean_squared_error(y_te, model.predict(X_te))))

    np.random.seed(42)

    idx = np.random.choice(len(X), min(600, len(X)), replace=False)

    X_samp = X.values[idx]

    y_samp = y[idx]

    explainer = shap.TreeExplainer(model)

    shap_vals = explainer.shap_values(X_samp)

    song_labels = (

        df["song"].values[idx] if "song" in df.columns

        else np.array([f"row {i}" for i in idx])

    )

    return model, X_samp, y_samp, shap_vals, feat_cols, r2, rmse, len(y), song_labels

with st.spinner("Model trainen en SHAP-waarden berekenen…"):

    model, X_samp, y_samp, shap_vals, feat_cols, r2, rmse, n_rows, song_labels = train_xgboost_model()

                                                                               


                                                                                

st.markdown("### SHAP Feature Importance")

st.markdown("""
**Wat is SHAP?** SHAP (SHapley Additive exPlanations) maakt zichtbaar *welke features
het meest bijdragen* aan de voorspelling van het model. Een groene bar duwt de
voorspelling omhoog; rood verlaagt hem. De diagonale lijn in de scatter rechts staat voor
perfecte voorspellingen.
""")

mean_abs_shap = np.abs(shap_vals).mean(axis=0)

mean_dir = shap_vals.mean(axis=0)

order = np.argsort(mean_abs_shap)

fig_shap = go.Figure(go.Bar(

    x=mean_abs_shap[order],

    y=[feat_cols[i] for i in order],

    orientation="h",

    marker_color=["#2ecc71" if mean_dir[i] >= 0 else "#e74c3c" for i in order],

    marker_opacity=0.85,

))

fig_shap.update_layout(

    **fig_layout(360),

    title="SHAP Feature Importance — energy target",

    xaxis_title="Gemiddelde |SHAP waarde|",

    yaxis=dict(tickfont=dict(size=10.5), **AXIS),

    xaxis=dict(**AXIS),

)

st.plotly_chart(fig_shap, use_container_width=True, config=dict(displayModeBar=False))

st.markdown('<p class="fig-cap">Figuur 3 — SHAP feature importance. Groen = verhoogt energy-voorspelling, rood = verlaagt.</p>', unsafe_allow_html=True)

                                                                                

st.markdown("### Feature gewichten aanpassen")

st.markdown("""
Hieronder zie je het AI-component dat wij willen gebruiken. Dit is een voorbeeld dat we hebben
gemaakt op een Spotify-dataset. Deze dataset lijkt qua opbouw sterk op de Chartmetric-data
die we daadwerkelijk willen gaan gebruiken.

De dataset bevat nummers van de afgelopen 24 jaar met bijbehorende audio-eigenschappen —
denk aan **loudness** (hoe hard een nummer klinkt), **tempo** (BPM), **danceability**,
**acousticness**, **year** en meer. Op basis van al die eigenschappen wil het model één
label voorspellen. In dit voorbeeld is dat **energy**: een getal tussen 0 en 1 dat aangeeft
hoe intens of energiek een nummer is.

Bij Chartmetric kiezen we straks de meest relevante label — bijvoorbeeld een score die
aangeeft of een artiest aan het groeien is of niet.
""")

st.markdown("""
<div class="callout">
<b>Ons model voorspelt als volgt, stap voor stap:</b><br><br>
<b>1. Data inladen</b> — alle nummers worden ingeladen met hun features (loudness, tempo, year, etc.).<br>
<b>2. Model trainen</b> — XGBoost leert patronen: welke combinatie van features leidt tot een hoge of lage energy-score?
Het model heeft hiervoor 80% van de data gezien en getest op de overige 20%.<br>
<b>3. Feature importance berekenen (SHAP)</b> — het model laat zien welke features het zwaarst meewegen.
In dit voorbeeld blijkt <em>loudness</em> de sterkste voorspeller: harde nummers zijn bijna altijd energiek.<br>
<b>4. Voorspelling maken</b> — voor elk nummer geeft het model een verwachte energy-waarde.
De scatter hierboven laat zien hoe dicht die voorspelling bij de werkelijke waarde zit.<br>
<b>5. Gewichten aanpassen (human-in-the-loop)</b> — via de sliders hieronder kun jij bepalen hoeveel
invloed elke feature heeft op de voorspelling. Zet een feature op 0.0 en hij wordt volledig genegeerd;
zet hem op 2.0 en zijn invloed wordt verdubbeld. De grafiek updatet direct mee.
</div>
""", unsafe_allow_html=True)

st.markdown("""
Pas het *gewicht* van elke feature aan: **1.0** = model default · **0.0** = genegeerd · **2.0** = dubbele invloed.
*(In dit voorbeeld wordt Spotify song-data gebruikt als stand-in voor de Chartmetric artiest-data,
die dezelfde structuur heeft.)*
""")

state_key = "bill_energy_weights"

for f in feat_cols:

    if f"{state_key}_{f}" not in st.session_state:

        st.session_state[f"{state_key}_{f}"] = 1.0

def reset_weights():

    for f in feat_cols:

        st.session_state[f"{state_key}_{f}"] = 1.0

col_sliders, col_scatter = st.columns([2, 3], gap="large")

with col_sliders:

    st.markdown("**Feature gewichten**")

    for feat in feat_cols:

        st.slider(

            feat,

            min_value=0.0, max_value=3.0, step=0.1,

            key=f"{state_key}_{feat}",

        )

    st.button("Reset alle gewichten", on_click=reset_weights, type="secondary")

multipliers = np.array(

    [st.session_state[f"{state_key}_{f}"] for f in feat_cols],

    dtype=np.float32,

)

y_pred_adj = model.predict(X_samp * multipliers)

with col_scatter:

    lo = float(min(y_samp.min(), y_pred_adj.min()))

    hi = float(max(y_samp.max(), y_pred_adj.max()))

    fig_adj = go.Figure()

    fig_adj.add_trace(go.Scatter(

        x=y_samp, y=y_pred_adj,

        mode="markers",

        text=song_labels,

        marker=dict(size=5, color="#8ab4f8", opacity=0.45),

        name="Songs",

        hovertemplate="<b>%{text}</b><br>Werkelijk: %{x:.3f}<br>Voorspeld: %{y:.3f}<extra></extra>",

    ))

    fig_adj.add_trace(go.Scatter(

        x=[lo, hi], y=[lo, hi],

        mode="lines",

        line=dict(color="#e74c3c", width=2, dash="dash"),

        name="Perfecte voorspelling",

    ))

    fig_adj.update_layout(

        **fig_layout(520),

        title="Werkelijk vs. Voorspeld — energy",

        xaxis_title="Werkelijke energy",

        yaxis_title="Voorspelde energy",

        xaxis=dict(**AXIS),

        yaxis=dict(**AXIS),

        legend=dict(orientation="h", y=1.05, x=0, font=dict(size=10)),

    )

    st.plotly_chart(fig_adj, use_container_width=True, config=dict(displayModeBar=False))

    changed = [f"**{f}** ×{v:.1f}" for f, v in zip(feat_cols, multipliers) if v != 1.0]

    if changed:

        st.info("Actief: " + " · ".join(changed))

st.markdown("""
<div class="callout callout-green">
<b>Wat we hier nog aan willen toevoegen:</b><br>
• Een makkelijke manier om een <em>rising star</em> of trending artiest te spotten.<br>
• Automatische <em>anomaly detection</em>: als een artiest ineens een spike krijgt in
volgers of streams, stuurt het systeem een waarschuwing zodat Lofi proactief kan handelen.
</div>
""", unsafe_allow_html=True)

st.markdown("---")

                                                                                

                              

                                                                                

st.markdown('<a name="resident-advisor-scraper"></a>', unsafe_allow_html=True)

st.markdown("## 3. Resident Advisor Scraper")

st.markdown("""
We scrapen events en lineups van **Resident Advisor** voor een selectie artiesten.
Dit geeft inzicht in de booking-frequentie, welke steden ze spelen, en met wie ze
op het podium staan. Combineer je dit met de AI-voorspelling en de Reddit-sentimentanalyse,
dan heb je een volledig profiel van een artiest.
""")

@st.cache_data(ttl=120)

def load_ra_data():

    ev_path = RA_DIR / "EventItem.jsonl"

    lu_path = RA_DIR / "EventLineupItem.jsonl"

    events, lineups = [], []

    for path, store in [(ev_path, events), (lu_path, lineups)]:

        if path.exists():

            for line in path.read_text(encoding="utf-8").splitlines():

                if line.strip():

                    store.append(json.loads(line))

    df = pd.DataFrame(events) if events else pd.DataFrame()

    lu = pd.DataFrame(lineups) if lineups else pd.DataFrame()

    if not df.empty:

        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        df["event_id"] = df["id"].astype(str).str.split("_").str[0]

    return df, lu

ra_df, ra_lu = load_ra_data()

if ra_df.empty:

    st.markdown('<div class="callout callout-amber">⚠️ Geen RA data gevonden. Zorg dat <code>EventItem.jsonl</code> in de scraper-map staat.</div>', unsafe_allow_html=True)

else:

    today = pd.Timestamp.today().normalize()

    ARTISTS_RA = sorted(ra_df["artist"].dropna().unique())

                                                                               

    st.markdown("### Artiest profiel")

    st.markdown("""
    Selecteer een artiest om het profiel te zien: verleden en toekomstige events,
    meest gespeelde steden en venues, en met wie hij/zij het vaakst samen speelt.
    """)

    sel_artist = st.selectbox("Selecteer artiest", ARTISTS_RA, key="ra_artist_sel")

    adf = ra_df[ra_df["artist"] == sel_artist].sort_values("date")

    future = adf[adf["date"] >= today]

    pc1, pc2, pc3 = st.columns(3)

    pc1.metric("Toekomstige events", len(future))

    pc2.metric("Steden", adf["city"].nunique() if "city" in adf.columns else "—")

    pc3.metric("Venues", adf["venue"].nunique() if "venue" in adf.columns else "—")

                                                                               

    if not future.empty and "date" in future.columns:

        fig_tl = go.Figure()

        fig_tl.add_trace(go.Scatter(

            x=future["date"],

            y=[sel_artist] * len(future),

            mode="markers",

            marker=dict(size=14, color="#2ecc71", symbol="circle", line=dict(color="#0d0d0f", width=2)),

            customdata=future[["title", "venue", "city"]].values if all(c in future.columns for c in ["title", "venue", "city"]) else None,

            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}, %{customdata[2]}<br>%{x|%d %b %Y}<extra></extra>"

            if all(c in future.columns for c in ["title", "venue", "city"]) else "%{x|%d %b %Y}<extra></extra>",

            name=sel_artist,

        ))

        fig_tl.update_layout(

            **fig_layout(180),

            title=f"Aankomende events — {sel_artist}",

            xaxis=dict(tickformat="%b %Y", dtick="M1", tickangle=-30, showgrid=True, **AXIS),

            yaxis=dict(showgrid=False, tickfont=dict(size=12), **AXIS),

            showlegend=False,

        )

        st.plotly_chart(fig_tl, use_container_width=True, config=dict(displayModeBar=False))

                                                                              

    st.markdown("### Aankomende events")

    DISPLAY_COLS = [c for c in ["date", "title", "venue", "city"] if c in adf.columns]

    if future.empty:

        st.info("Geen aankomende events gevonden voor deze artiest.")

    else:

        show_f = future[DISPLAY_COLS].copy()

        show_f["date"] = show_f["date"].dt.strftime("%d %b %Y")

        show_f.columns = [c.capitalize() for c in show_f.columns]

        st.dataframe(show_f.reset_index(drop=True), use_container_width=True, hide_index=True)

                                                                               

    col_l, col_r = st.columns(2)

    with col_l:

        if "city" in adf.columns:

            st.markdown("### Top steden")

            city_c = adf["city"].value_counts().head(10).reset_index()

            city_c.columns = ["city", "count"]

            fig_city = go.Figure(go.Bar(

                x=city_c["count"], y=city_c["city"],

                orientation="h",

                marker_color="#3a6bc4", marker_opacity=0.82,

            ))

            fig_city.update_layout(

                **fig_layout(320),

                title="Meest gespeelde steden",

                yaxis=dict(autorange="reversed", tickfont=dict(size=11), **AXIS),

                xaxis=dict(**AXIS),

            )

            st.plotly_chart(fig_city, use_container_width=True, config=dict(displayModeBar=False))

    with col_r:

        if not ra_lu.empty and "lineup" in ra_lu.columns:

            st.markdown("### Meest gespeelde collega's")

            eids = set(adf["event_id"].astype(str))

            co_rows = ra_lu[ra_lu["id"].astype(str).isin(eids)]

            coartists = Counter(

                a for row in co_rows["lineup"].dropna()

                for a in (row if isinstance(row, list) else [])

                if a != sel_artist

            )

            if coartists:

                co_df = pd.DataFrame(coartists.most_common(12), columns=["artist", "count"])

                fig_co = go.Figure(go.Bar(

                    x=co_df["count"], y=co_df["artist"],

                    orientation="h",

                    marker_color="#8ab4f8", marker_opacity=0.78,

                ))

                fig_co.update_layout(

                    **fig_layout(320),

                    title=f"Co-performers — {sel_artist}",

                    yaxis=dict(autorange="reversed", tickfont=dict(size=11), **AXIS),

                    xaxis=dict(**AXIS),

                )

                st.plotly_chart(fig_co, use_container_width=True, config=dict(displayModeBar=False))

            else:

                st.info("Geen lineup-data beschikbaar.")

    st.markdown("""
<div class="callout callout-green">
<b>Roadmap RA Scraper:</b><br>
• AI-voorspelling vanuit het XGBoost model wordt gekoppeld aan het artiest-profiel.<br>
• Reddit-sentimentanalyse wordt toegevoegd per artiest.<br>
• <b>Artist Recommendation System:</b> op basis van lineup-combinaties en model-output
geeft het systeem advies over de beste boekingscombinaties én de <em>hidden gems</em> —
de outliers die verrassend goed passen maar nog onder de radar zitten.<br>
• Zo krijg je één volledig overzicht: upcoming events + lineup-combinaties + sentiment —
zodat Lofi direct kan inschatten of een artiest goed bij jullie past.
</div>
""", unsafe_allow_html=True)

st.markdown("---")

                                                                                

                    

                                                                                

st.markdown('<a name="reddit-scraper"></a>', unsafe_allow_html=True)

st.markdown("## 4. Reddit Scraper  <span class='badge-wip'>Work in progress</span>", unsafe_allow_html=True)

st.markdown("""
Subreddits worden gescraped op basis van een artiest-keyword. Over de gevonden posts en
comments draait vervolgens een sentimentanalyse — zo weten we hoe de community over een
artiest denkt.
""")

st.markdown("""
<div class="callout callout-amber">
⚙️ &nbsp;<b>Work in progress.</b> De Reddit-scraper en sentimentpipeline worden momenteel
ontwikkeld. Binnenkort hier zichtbaar.
</div>
""", unsafe_allow_html=True)

st.markdown("---")

                                                                                

                   

                                                                                

st.markdown('<a name="llm-assistent"></a>', unsafe_allow_html=True)

st.markdown("## 5. LLM Assistent  <span class='badge-wip'>Coming soon</span>", unsafe_allow_html=True)

st.markdown("""
Een chatbot gekoppeld aan de Lofi Airtable en de outputs van onze scrapers en modellen.
Via een eenvoudig chatinterface geef je advies, beantwoord je vragen en analyseer je
de output — zonder dat je zelf door spreadsheets hoeft te zoeken.
""")

st.markdown("""
<div class="callout callout-amber">
💬 &nbsp;<b>Coming soon.</b> De LLM-assistent wordt aangesloten op Airtable en de scraper-outputs.
</div>
""", unsafe_allow_html=True)

st.markdown("---")

st.markdown(

    '<p style="text-align:center;font-size:9pt;color:#888;font-family:Calibri,sans-serif;">'

    'Armadillo × Lofi · Pipeline Demo · 2026 · Intern document</p>',

    unsafe_allow_html=True,

)

