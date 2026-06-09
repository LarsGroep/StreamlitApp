"""
RA Event Dashboard — scraped event data visualiser
Run: streamlit run dashboard.py   (from the scraper/ directory)
"""

import json
import itertools
from pathlib import Path
from collections import Counter

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ── page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="RA Events",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── theme ──────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=JetBrains+Mono:ital,wght@0,300;0,400;0,500;0,700;1,300&display=swap');

:root {
    --bg:      #070709;
    --bg2:     #0e0e12;
    --bg3:     #16161c;
    --accent:  #c6ff2f;
    --accent2: #ff2f6e;
    --accent3: #2ff5ff;
    --text:    #d8d8e0;
    --muted:   #484858;
    --border:  #1e1e28;
}

/* ── global ── */
html, body,
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section.main > div { background: var(--bg) !important; }

* { font-family: 'JetBrains Mono', monospace !important; color: var(--text); }

[data-testid="stHeader"],
[data-testid="stToolbar"] { background: var(--bg) !important; border-bottom: 1px solid var(--border) !important; }

/* ── sidebar ── */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div { background: var(--bg2) !important; border-right: 1px solid var(--border) !important; }
[data-testid="stSidebar"] label { font-size: 0.6rem !important; text-transform: uppercase !important; letter-spacing: 0.2em !important; color: var(--muted) !important; }

/* ── headings ── */
h1 {
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: 3.6rem !important;
    letter-spacing: 0.06em !important;
    color: var(--accent) !important;
    line-height: 0.95 !important;
    margin-bottom: 0 !important;
}
h2, h3 {
    font-family: 'Bebas Neue', sans-serif !important;
    color: var(--text) !important;
    letter-spacing: 0.1em !important;
    margin-top: 0 !important;
}
h2 { font-size: 1.6rem !important; }
h3 { font-size: 1.2rem !important; color: var(--muted) !important; }

/* ── metrics ── */
[data-testid="stMetric"] {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-top: 2px solid var(--accent) !important;
    padding: 1rem 1.2rem !important;
    border-radius: 0 !important;
}
[data-testid="stMetricLabel"] > div {
    font-size: 0.58rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.2em !important;
    color: var(--muted) !important;
}
[data-testid="stMetricValue"] > div {
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: 2.4rem !important;
    color: var(--accent) !important;
    letter-spacing: 0.04em !important;
}
[data-testid="stMetricDelta"] > div { font-size: 0.65rem !important; }

/* ── tabs ── */
[data-baseweb="tab-list"] {
    background: var(--bg2) !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
}
[data-baseweb="tab"] {
    color: var(--muted) !important;
    font-size: 0.65rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.15em !important;
    padding: 0.6rem 1.4rem !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
}
[aria-selected="true"][data-baseweb="tab"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
    background: var(--bg3) !important;
}

/* ── dataframes ── */
.stDataFrame iframe { background: var(--bg2) !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--border) !important; }

/* ── selectbox / multiselect ── */
[data-baseweb="select"] > div {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 0 !important;
    color: var(--text) !important;
}
[data-baseweb="popover"] { background: var(--bg3) !important; border: 1px solid var(--border) !important; }
[data-baseweb="option"] { background: var(--bg3) !important; }
[data-baseweb="option"]:hover { background: var(--bg2) !important; }

/* ── slider ── */
[data-baseweb="slider"] [role="slider"] { background: var(--accent) !important; }
[data-baseweb="slider"] div[data-testid="stSlider"] div { background: var(--accent) !important; }

/* ── divider ── */
hr { border-color: var(--border) !important; margin: 1.5rem 0 !important; }

/* ── caption / small ── */
small, .stCaption { color: var(--muted) !important; font-size: 0.6rem !important; letter-spacing: 0.05em !important; }

/* ── expander ── */
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 0 !important;
    background: var(--bg2) !important;
}
[data-testid="stExpander"] summary { font-size: 0.7rem !important; text-transform: uppercase !important; letter-spacing: 0.12em !important; }

/* ── plotly containers ── */
.js-plotly-plot .plotly { background: transparent !important; }

/* ── section label ── */
.section-label {
    font-size: 0.55rem;
    text-transform: uppercase;
    letter-spacing: 0.25em;
    color: var(--muted);
    border-left: 2px solid var(--accent);
    padding-left: 0.6rem;
    margin-bottom: 0.4rem;
    line-height: 1;
}
.section-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.8rem;
    letter-spacing: 0.1em;
    color: var(--text);
    line-height: 1;
    margin-bottom: 1.2rem;
}
.event-pill {
    display: inline-block;
    background: var(--bg3);
    border: 1px solid var(--border);
    padding: 0.15rem 0.5rem;
    font-size: 0.6rem;
    letter-spacing: 0.05em;
    color: var(--muted);
    margin: 1px;
}
</style>
""", unsafe_allow_html=True)

# ── plotly base theme ──────────────────────────────────────────────────────────

AXIS_DEFAULTS = dict(gridcolor="#1e1e28", linecolor="#1e1e28", tickcolor="#484858", zerolinecolor="#1e1e28")

PLOTLY_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#0e0e12",
    font=dict(family="JetBrains Mono", color="#d8d8e0", size=11),
    hoverlabel=dict(bgcolor="#16161c", bordercolor="#1e1e28", font=dict(family="JetBrains Mono", size=11)),
    margin=dict(l=4, r=4, t=28, b=4),
)

ARTIST_PALETTE = [
    "#c6ff2f", "#ff2f6e", "#2ff5ff", "#ff8c2f", "#a02fff",
    "#ff2f2f", "#2fbaff", "#ffe02f", "#ff2fd0", "#2fff8c",
]


# ── data loading ───────────────────────────────────────────────────────────────

BASE = Path(__file__).parent


@st.cache_data(ttl=60)
def load_data():
    events, lineups = [], []
    for path, store in [(BASE / "EventItem.jsonl", events), (BASE / "EventLineupItem.jsonl", lineups)]:
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    store.append(json.loads(line))

    df = pd.DataFrame(events) if events else pd.DataFrame()
    lu = pd.DataFrame(lineups) if lineups else pd.DataFrame()

    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df["month_label"] = df["date"].dt.strftime("%b %Y")
        df["month_sort"] = df["date"].dt.to_period("M").astype(str)
        # composite id format: "{event_id}_{artist_slug}" — strip suffix for lineup join
        df["event_id"] = df["id"].str.split("_").str[0]

    return df, lu


df, lu = load_data()

if df.empty:
    st.error("No data found. Run `scrapy crawl ra_artist_spider` first, then refresh.")
    st.stop()

# ── derived data ───────────────────────────────────────────────────────────────

ARTISTS = sorted(df["artist"].unique())
COLOR_MAP = {a: ARTIST_PALETTE[i % len(ARTIST_PALETTE)] for i, a in enumerate(ARTISTS)}

# Join events with lineups (event_id strips the artist-slug suffix from composite ids)
df_lu = df.merge(lu, left_on="event_id", right_on="id", how="left").drop(columns=["id_y"], errors="ignore").rename(columns={"id_x": "id"})


def top_coartists(artist_name, n=12):
    eids = set(df[df["artist"] == artist_name]["event_id"])
    rows = lu[lu["id"].isin(eids)]
    counts = Counter(
        a for row in rows["lineup"].dropna()
        for a in row
        if a != artist_name
    )
    return pd.DataFrame(counts.most_common(n), columns=["artist", "count"])


def cooccurrence_matrix():
    tracked = set(ARTISTS)
    cooc = Counter()
    for _, row in df_lu.iterrows():
        if not isinstance(row.get("lineup"), list):
            continue
        in_lineup = (set(row["lineup"]) & tracked) | {row["artist"]}
        for a, b in itertools.combinations(sorted(in_lineup), 2):
            cooc[(a, b)] += 1
    mat = pd.DataFrame(0, index=ARTISTS, columns=ARTISTS)
    for (a, b), c in cooc.items():
        if a in mat.index and b in mat.columns:
            mat.loc[a, b] = c
            mat.loc[b, a] = c
    return mat


# ── sidebar filters ────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown('<div class="section-label">Filters</div>', unsafe_allow_html=True)
    sel_artists = st.multiselect("Artists", ARTISTS, default=ARTISTS)

    date_min = df["date"].min().date()
    date_max = df["date"].max().date()
    date_range = st.date_input("Date range", value=(date_min, date_max), min_value=date_min, max_value=date_max)

    cities = sorted(df["city"].dropna().unique())
    sel_cities = st.multiselect("Cities", cities, default=[])

    st.markdown("---")
    st.markdown('<div class="section-label">Display</div>', unsafe_allow_html=True)
    show_links = st.checkbox("Show RA links", value=True)

# ── apply filters ──────────────────────────────────────────────────────────────

fdf = df[df["artist"].isin(sel_artists)]
if len(date_range) == 2:
    fdf = fdf[(fdf["date"].dt.date >= date_range[0]) & (fdf["date"].dt.date <= date_range[1])]
if sel_cities:
    fdf = fdf[fdf["city"].isin(sel_cities)]

fdf = fdf.sort_values("date")

# ── header ─────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-label">Resident Advisor — Event Intelligence</div>', unsafe_allow_html=True)
st.markdown("# RA EVENTS")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Events", len(fdf))
c2.metric("Artists", fdf["artist"].nunique())
c3.metric("Cities", fdf["city"].nunique())
c4.metric("Venues", fdf["venue"].nunique())
c5.metric("Date span", f"{(fdf['date'].max() - fdf['date'].min()).days}d" if len(fdf) > 1 else "—")

st.markdown("---")

# ── tabs ───────────────────────────────────────────────────────────────────────

tab_tl, tab_geo, tab_lineup, tab_table = st.tabs([
    "◎  Timeline", "⊕  Geography", "⧉  Lineup", "≡  Events"
])


# ── TAB 1: TIMELINE ───────────────────────────────────────────────────────────

with tab_tl:
    st.markdown('<div class="section-label">Upcoming events plotted by date</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">ARTIST SCHEDULE</div>', unsafe_allow_html=True)

    if fdf.empty:
        st.info("No events match the current filters.")
    else:
        fig = go.Figure()

        # Artist order: by number of events descending
        order = fdf.groupby("artist").size().sort_values(ascending=True).index.tolist()

        for artist in order:
            adf = fdf[fdf["artist"] == artist].sort_values("date")
            color = COLOR_MAP[artist]

            # Connecting line
            fig.add_trace(go.Scatter(
                x=adf["date"],
                y=[artist] * len(adf),
                mode="lines",
                line=dict(color=color, width=0.8, dash="dot"),
                showlegend=False,
                hoverinfo="skip",
                opacity=0.35,
            ))

            # Event markers
            fig.add_trace(go.Scatter(
                x=adf["date"],
                y=[artist] * len(adf),
                mode="markers",
                name=artist,
                marker=dict(
                    size=13,
                    color=color,
                    symbol="circle",
                    line=dict(color="#070709", width=1.5),
                    opacity=0.92,
                ),
                customdata=adf[["title", "venue", "city", "link"]].values,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "<span style='color:#888'>%{customdata[1]}</span><br>"
                    "<span style='color:#aaa'>%{customdata[2]}</span><br>"
                    "<span style='color:#666'>%{x|%a %d %b %Y}</span>"
                    "<extra><b style='color:" + color + "'>%{fullData.name}</b></extra>"
                ),
            ))

        # Today line
        today = pd.Timestamp.today().strftime("%Y-%m-%d")
        fig.add_shape(
            type="line", x0=today, x1=today, y0=0, y1=1,
            xref="x", yref="paper",
            line=dict(color="#484858", width=1, dash="solid"),
        )
        fig.add_annotation(
            x=today, y=1, xref="x", yref="paper",
            text="TODAY", showarrow=False,
            font=dict(size=9, color="#484858"),
            xanchor="left", yanchor="top",
        )

        fig.update_layout(
            **PLOTLY_BASE,
            height=max(320, len(order) * 52 + 80),
            showlegend=True,
            legend=dict(
                orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
                font=dict(size=10), bgcolor="rgba(0,0,0,0)", bordercolor="#1e1e28", borderwidth=1,
            ),
            xaxis=dict(
                **AXIS_DEFAULTS,
                tickformat="%b %Y",
                dtick="M1",
                tickangle=-30,
                showgrid=True,
            ),
            yaxis=dict(
                **AXIS_DEFAULTS,
                showgrid=False,
                tickfont=dict(size=10.5, color="#d8d8e0"),
            ),
        )
        st.plotly_chart(fig, use_container_width=True, config=dict(displayModeBar=False))

    st.markdown("---")
    st.markdown('<div class="section-label">Events per month, by artist</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">MONTHLY DENSITY</div>', unsafe_allow_html=True)

    if not fdf.empty:
        month_counts = (
            fdf.groupby(["month_sort", "month_label", "artist"])
            .size()
            .reset_index(name="count")
            .sort_values("month_sort")
        )

        month_order = month_counts["month_label"].tolist()
        fig2 = px.bar(
            month_counts, x="month_label", y="count", color="artist",
            color_discrete_map=COLOR_MAP,
            barmode="stack",
            labels={"month_label": "", "count": "Events", "artist": ""},
            category_orders={"month_label": month_order},
        )
        fig2.update_layout(
            **PLOTLY_BASE,
            height=300,
            bargap=0.25,
            xaxis=dict(**AXIS_DEFAULTS, tickangle=-30, tickfont=dict(size=10)),
            yaxis=dict(**AXIS_DEFAULTS),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
                font=dict(size=9), bgcolor="rgba(0,0,0,0)", bordercolor="#1e1e28", borderwidth=1,
            ),
        )
        fig2.update_traces(marker_line_width=0)
        st.plotly_chart(fig2, use_container_width=True, config=dict(displayModeBar=False))


# ── TAB 2: GEOGRAPHY ─────────────────────────────────────────────────────────

with tab_geo:
    left, right = st.columns(2)

    with left:
        st.markdown('<div class="section-label">Top cities by event count</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">CITIES</div>', unsafe_allow_html=True)

        city_counts = fdf["city"].value_counts().head(20).reset_index()
        city_counts.columns = ["city", "count"]

        fig = go.Figure(go.Bar(
            x=city_counts["count"],
            y=city_counts["city"],
            orientation="h",
            marker=dict(
                color=city_counts["count"],
                colorscale=[[0, "#1e1e28"], [0.4, "#484858"], [1, "#c6ff2f"]],
                showscale=False,
            ),
            text=city_counts["count"],
            textposition="outside",
            textfont=dict(size=10, color="#484858"),
            hovertemplate="<b>%{y}</b>: %{x} events<extra></extra>",
        ))
        fig.update_layout(
            **PLOTLY_BASE,
            height=500,
            yaxis=dict(
                **AXIS_DEFAULTS,
                categoryorder="total ascending",
                showgrid=False,
                tickfont=dict(size=10.5),
            ),
            xaxis=dict(**AXIS_DEFAULTS, showgrid=True),
        )
        st.plotly_chart(fig, use_container_width=True, config=dict(displayModeBar=False))

    with right:
        st.markdown('<div class="section-label">Top venues by event count</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">VENUES</div>', unsafe_allow_html=True)

        venue_counts = fdf["venue"].value_counts().head(20).reset_index()
        venue_counts.columns = ["venue", "count"]

        fig = go.Figure(go.Bar(
            x=venue_counts["count"],
            y=venue_counts["venue"],
            orientation="h",
            marker=dict(
                color=venue_counts["count"],
                colorscale=[[0, "#1e1e28"], [0.4, "#2f3844"], [1, "#2ff5ff"]],
                showscale=False,
            ),
            text=venue_counts["count"],
            textposition="outside",
            textfont=dict(size=10, color="#484858"),
            hovertemplate="<b>%{y}</b>: %{x} events<extra></extra>",
        ))
        fig.update_layout(
            **PLOTLY_BASE,
            height=500,
            yaxis=dict(
                **AXIS_DEFAULTS,
                categoryorder="total ascending",
                showgrid=False,
                tickfont=dict(size=10.5),
            ),
            xaxis=dict(**AXIS_DEFAULTS, showgrid=True),
        )
        st.plotly_chart(fig, use_container_width=True, config=dict(displayModeBar=False))

    st.markdown("---")
    st.markdown('<div class="section-label">Events per city, broken down by artist</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">CITY × ARTIST BREAKDOWN</div>', unsafe_allow_html=True)

    top_cities_list = city_counts.head(12)["city"].tolist()
    city_artist = (
        fdf[fdf["city"].isin(top_cities_list)]
        .groupby(["city", "artist"])
        .size()
        .reset_index(name="count")
    )
    city_totals = city_artist.groupby("city")["count"].sum().sort_values(ascending=False)
    city_artist["city"] = pd.Categorical(city_artist["city"], categories=city_totals.index, ordered=True)

    fig = px.bar(
        city_artist.sort_values("city"),
        x="city", y="count", color="artist",
        color_discrete_map=COLOR_MAP,
        barmode="stack",
        labels={"city": "", "count": "Events", "artist": ""},
    )
    fig.update_layout(
        **PLOTLY_BASE,
        height=320,
        bargap=0.3,
        xaxis=dict(**AXIS_DEFAULTS, tickangle=-30, tickfont=dict(size=10.5)),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0, font=dict(size=9), bgcolor="rgba(0,0,0,0)", bordercolor="#1e1e28", borderwidth=1),
    )
    fig.update_traces(marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True, config=dict(displayModeBar=False))


# ── TAB 3: LINEUP ────────────────────────────────────────────────────────────

with tab_lineup:

    # ── co-occurrence heatmap ─────────────────────────────────────────────────
    st.markdown('<div class="section-label">Tracked artists sharing the same event bill</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">ARTIST CO-OCCURRENCE</div>', unsafe_allow_html=True)

    cooc = cooccurrence_matrix()

    fig = go.Figure(go.Heatmap(
        z=cooc.values,
        x=cooc.columns.tolist(),
        y=cooc.index.tolist(),
        colorscale=[[0, "#0e0e12"], [0.01, "#1a1a28"], [0.3, "#2f3844"], [0.7, "#6b9e3e"], [1, "#c6ff2f"]],
        showscale=True,
        colorbar=dict(
            thickness=10, len=0.8,
            tickfont=dict(size=9, color="#484858"),
            outlinewidth=0,
        ),
        hovertemplate="<b>%{y}</b> × <b>%{x}</b><br>Shared events: %{z}<extra></extra>",
        text=cooc.values,
        texttemplate="%{text}",
        textfont=dict(size=11),
    ))
    fig.update_layout(
        **PLOTLY_BASE,
        height=480,
        xaxis=dict(
            **AXIS_DEFAULTS,
            showgrid=False, tickangle=-35, tickfont=dict(size=10),
            side="bottom",
        ),
        yaxis=dict(
            **AXIS_DEFAULTS,
            showgrid=False, tickfont=dict(size=10),
            autorange="reversed",
        ),
    )
    st.plotly_chart(fig, use_container_width=True, config=dict(displayModeBar=False))

    st.markdown("---")

    # ── per-artist co-performers ──────────────────────────────────────────────
    st.markdown('<div class="section-label">Most frequent co-performers per artist</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">CO-PERFORMERS</div>', unsafe_allow_html=True)

    sel_artist = st.selectbox("Select artist", ARTISTS, key="coart_sel")
    coart_df = top_coartists(sel_artist, n=15)

    if coart_df.empty:
        st.info("No lineup data available for this artist.")
    else:
        color = COLOR_MAP[sel_artist]
        fig = go.Figure(go.Bar(
            x=coart_df["count"],
            y=coart_df["artist"],
            orientation="h",
            marker=dict(
                color=coart_df["count"],
                colorscale=[[0, "#1a1a28"], [1, color]],
                showscale=False,
            ),
            text=coart_df["count"],
            textposition="outside",
            textfont=dict(size=10, color="#484858"),
            hovertemplate="<b>%{y}</b>: %{x} shared events<extra></extra>",
        ))
        fig.update_layout(
            **PLOTLY_BASE,
            height=420,
            yaxis=dict(
                **AXIS_DEFAULTS,
                categoryorder="total ascending",
                showgrid=False,
                tickfont=dict(size=11),
            ),
            xaxis=dict(**AXIS_DEFAULTS, showgrid=True, tickfont=dict(size=10)),
        )
        st.plotly_chart(fig, use_container_width=True, config=dict(displayModeBar=False))

    st.markdown("---")

    # ── event lineup cards ────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Full lineup per event</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">EVENT LINEUPS</div>', unsafe_allow_html=True)

    artist_filter = st.selectbox("Artist", ["All"] + ARTISTS, key="lineup_artist")
    ev_df = fdf.copy() if artist_filter == "All" else fdf[fdf["artist"] == artist_filter].copy()
    ev_df = ev_df.merge(lu, on="id", how="left").sort_values("date")

    for _, row in ev_df.iterrows():
        lineup = row.get("lineup")
        if not isinstance(lineup, list):
            lineup = []
        date_str = row["date"].strftime("%a %d %b %Y")
        color = COLOR_MAP.get(row["artist"], "#c6ff2f")
        pills = "".join(
            f'<span class="event-pill" style="color:{"#c6ff2f" if a == row["artist"] else "#888"}">{a}</span>'
            for a in lineup
        ) if lineup else '<span class="event-pill">— no lineup data —</span>'

        with st.expander(f"{date_str}  ·  {row['title']}  ·  {row['venue']}, {row['city']}"):
            link_html = f'<a href="{row["link"]}" target="_blank" style="color:{color};font-size:0.6rem;letter-spacing:0.1em">→ RA.CO/{row["id"]}</a>' if show_links else ""
            st.markdown(
                f'<div style="margin-bottom:0.4rem">'
                f'<span style="color:{color};font-family:\'Bebas Neue\',sans-serif;font-size:1.1rem;letter-spacing:0.08em">{row["artist"]}</span>'
                f'&nbsp;&nbsp;{link_html}'
                f'</div>'
                f'<div style="line-height:2">{pills}</div>',
                unsafe_allow_html=True,
            )


# ── TAB 4: EVENTS TABLE ───────────────────────────────────────────────────────

with tab_table:
    st.markdown('<div class="section-label">All scraped events</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">EVENT LISTING</div>', unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        tbl_artist = st.multiselect("Artist", ARTISTS, default=ARTISTS, key="tbl_artist")
    with col_b:
        tbl_cities = sorted(fdf["city"].dropna().unique())
        tbl_city = st.multiselect("City", tbl_cities, default=[], key="tbl_city")
    with col_c:
        tbl_sort = st.selectbox("Sort by", ["Date ↑", "Date ↓", "Artist", "City", "Venue"], key="tbl_sort")

    tbl = fdf[fdf["artist"].isin(tbl_artist)].copy()
    if tbl_city:
        tbl = tbl[tbl["city"].isin(tbl_city)]

    sort_map = {
        "Date ↑": ("date", True),
        "Date ↓": ("date", False),
        "Artist": ("artist", True),
        "City": ("city", True),
        "Venue": ("venue", True),
    }
    scol, sasc = sort_map[tbl_sort]
    tbl = tbl.sort_values(scol, ascending=sasc)

    display = tbl[["date", "artist", "title", "venue", "city"]].copy()
    display["date"] = display["date"].dt.strftime("%a %d %b %Y")
    display.columns = ["Date", "Artist", "Event", "Venue", "City"]

    if show_links:
        display["Link"] = tbl["link"].apply(lambda u: f"[→ ra.co]({u})")

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Link": st.column_config.LinkColumn("Link", display_text="→ ra.co"),
        } if show_links else {},
        height=min(600, 35 * len(display) + 40),
    )

    st.markdown(
        f'<div style="text-align:right;margin-top:0.4rem"><small>{len(display)} events</small></div>',
        unsafe_allow_html=True,
    )
