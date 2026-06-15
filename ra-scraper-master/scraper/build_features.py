"""
Builds the enriched feature matrix (features.csv) for Isolation Forest training.
Joins data from all scraped sources per artist.

Run after all spiders + lastfm_scraper.py:
    python build_features.py
"""

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent

# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def load_artists():
    seed = set()
    for line in (HERE / "artists.txt").read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if name and not name.startswith("#"):
            seed.add(name.lower())
    return seed


# ---------------------------------------------------------------------------
# Per-artist aggregations
# ---------------------------------------------------------------------------

VOTE_MAP = {"geweldig": 5, "goed": 4, "redelijk": 3, "matig": 2, "slecht": 1}

TECHNO_TAGS = {
    "techno", "tech house", "tech-house", "dark techno", "dark-techno",
    "hard techno", "hard-techno", "industrial techno", "industrial-techno",
    "minimal techno", "minimal-techno", "acid techno", "acid-techno",
    "dub techno", "dub-techno", "deep tech", "deep-tech",
    "electro", "house", "deep house", "deep-house", "progressive house",
    "minimal", "ambient techno", "modular",
}


def build_lastfm_features(rows):
    out = {}
    for r in rows:
        key = r.get("name", "").lower().strip()
        if not key:
            continue
        listeners = int(r.get("listeners") or 0)
        playcount = int(r.get("playcount") or 0)
        tags = [t.lower() for t in (r.get("tags") or [])]
        out[key] = {
            "lfm_listeners": listeners,
            "lfm_playcount": playcount,
            "lfm_plays_per_listener": round(playcount / listeners, 3) if listeners > 0 else 0,
            "lfm_log_listeners": round(math.log1p(listeners), 4),
            "lfm_log_playcount": round(math.log1p(playcount), 4),
            "lfm_tag_count": len(tags),
            "lfm_similar_count": len(r.get("similar") or []),
            "lfm_has_techno_tag": int(bool(set(tags) & TECHNO_TAGS)),
        }
    return out


def build_pf_artist_features(rows):
    out = {}
    for r in rows:
        key = (r.get("artist") or "").lower().strip()
        if not key:
            continue
        genres = [g.lower() for g in (r.get("genres") or [])]
        out[key] = {
            "pf_fans": int(r.get("fans") or 0),
            "pf_past_perfs": int(r.get("past_performances") or 0),
            "pf_upcoming_perfs": int(r.get("upcoming_performances") or 0),
            "pf_photos": int(r.get("photos") or 0),
            "pf_videos": int(r.get("videos") or 0),
            "pf_vote_score": VOTE_MAP.get(r.get("vote_result"), 0),
            "pf_genre_count": len(genres),
            "pf_log_fans": round(math.log1p(int(r.get("fans") or 0)), 4),
            "pf_log_past": round(math.log1p(int(r.get("past_performances") or 0)), 4),
        }
    return out


def build_pf_event_features(rows):
    """Aggregate per-artist stats from the full event archive."""
    by_artist = defaultdict(list)
    for r in rows:
        key = (r.get("artist") or "").lower().strip()
        if key:
            by_artist[key].append(r)

    out = {}
    years = [2021, 2022, 2023, 2024, 2025]
    for artist, events in by_artist.items():
        countries = [e.get("country") for e in events if e.get("country")]
        cities = [e.get("city") for e in events if e.get("city")]
        total = len(events)

        nl_count = sum(1 for c in countries if c == "NL")
        nl_ratio = round(nl_count / total, 3) if total > 0 else 0

        unique_countries = len(set(countries))
        unique_cities = len(set(cities))
        geo_spread = round(unique_countries / total, 4) if total > 0 else 0

        year_counts = Counter(
            e.get("start_date", "")[:4]
            for e in events
            if e.get("start_date")
        )
        yr_vals = [int(year_counts.get(str(y), 0)) for y in years]

        # Linear trend slope across yearly event counts (events growth trajectory)
        if sum(yr_vals) > 0:
            x = np.array(years, dtype=float)
            y = np.array(yr_vals, dtype=float)
            x_c = x - x.mean()
            slope = float(np.dot(x_c, y) / np.dot(x_c, x_c)) if np.dot(x_c, x_c) != 0 else 0.0
        else:
            slope = 0.0

        feat = {
            "pf_total_events": total,
            "pf_unique_countries": unique_countries,
            "pf_unique_cities": unique_cities,
            "pf_nl_ratio": nl_ratio,
            "pf_geo_spread": geo_spread,
            "pf_events_trend_slope": round(slope, 4),
            "pf_log_total_events": round(math.log1p(total), 4),
        }
        for yr, val in zip(years, yr_vals):
            feat[f"pf_events_{yr}"] = val

        out[artist] = feat
    return out


def build_ra_features(rows):
    by_artist = defaultdict(list)
    for r in rows:
        key = (r.get("artist") or "").lower().strip()
        if key:
            by_artist[key].append(r)

    out = {}
    for artist, events in by_artist.items():
        cities = [e.get("city") for e in events if e.get("city")]
        out[artist] = {
            "ra_upcoming_events": len(events),
            "ra_unique_cities": len(set(cities)),
        }
    return out


def load_lofi_labels():
    path = HERE / "lofi_booked_labels.csv"
    if not path.exists():
        return {}
    out = {}
    import csv
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = row["artist"].lower().strip()
            out[key] = {
                "lofi_booked": int(row["lofi_booked"]),
                "lofi_appearance_count": int(row["lofi_appearance_count"]),
            }
    return out


def build_co_appearance_features(lineup_rows, seed_set):
    """Count how many times each artist co-appeared with seeds in last 5 years."""
    co_count = Counter()
    for event in lineup_rows:
        lineup = [a.lower().strip() for a in (event.get("lineup") or [])]
        seeds_present = [a for a in lineup if a in seed_set]
        non_seeds = [a for a in lineup if a not in seed_set]
        if seeds_present:
            for a in non_seeds:
                co_count[a] += 1
    out = {}
    for artist, count in co_count.items():
        out[artist] = {"co_appearances_with_seeds": count}
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    seed_set = load_artists()

    lfm_rows   = load_jsonl(HERE / "lastfm" / "LastFMSnapshot.jsonl")
    pf_art     = load_jsonl(HERE / "PartyflockArtistItem.jsonl")
    pf_ev      = load_jsonl(HERE / "PartyflockEventItem.jsonl")
    pf_lineup  = load_jsonl(HERE / "PartyflockLineupItem.jsonl")
    ra_ev      = load_jsonl(HERE / "EventItem.jsonl")

    # Keep only most-recent Last.fm snapshot per artist
    latest_lfm = {}
    for r in lfm_rows:
        key = r.get("name", "").lower().strip()
        if key not in latest_lfm or r["scraped_at"] > latest_lfm[key]["scraped_at"]:
            latest_lfm[key] = r
    lfm_rows = list(latest_lfm.values())

    lfm_feat    = build_lastfm_features(lfm_rows)
    pf_art_feat = build_pf_artist_features(pf_art)
    pf_ev_feat  = build_pf_event_features(pf_ev)
    ra_feat     = build_ra_features(ra_ev)
    co_feat     = build_co_appearance_features(pf_lineup, seed_set)
    lofi_labels = load_lofi_labels()

    # Union of all artist names from Last.fm (primary) + Partyflock
    all_keys = set(lfm_feat.keys()) | set(pf_art_feat.keys())

    rows = []
    for key in sorted(all_keys):
        # Skip artists flagged as mainstream
        lfm = lfm_feat.get(key, {})
        if lfm.get("lfm_listeners", 0) > 1_500_000:
            continue

        # Display name: prefer Last.fm canonical name
        lfm_row = latest_lfm.get(key, {})
        display_name = lfm_row.get("name") or key

        row = {"artist": display_name, "is_seed": int(key in seed_set)}
        row.update(lfm)
        row.update(pf_art_feat.get(key, {}))
        row.update(pf_ev_feat.get(key, {}))
        row.update(ra_feat.get(key, {}))
        row.update(co_feat.get(key, {}))
        row.update(lofi_labels.get(key, {"lofi_booked": 0, "lofi_appearance_count": 0}))
        rows.append(row)

    df = pd.DataFrame(rows)

    # Mark which artists have a Partyflock profile
    df["has_pf_profile"] = df["pf_fans"].notna().astype(int) if "pf_fans" in df.columns else 0
    df["has_ra_data"] = df["ra_upcoming_events"].notna().astype(int) if "ra_upcoming_events" in df.columns else 0

    # Drop columns that are 100% null (never populated)
    before = df.shape[1]
    df = df.dropna(axis=1, how="all")
    print(f"Dropped {before - df.shape[1]} fully-null columns")

    # Fill remaining nulls with 0 for numeric columns
    num_cols = df.select_dtypes(include="number").columns
    df[num_cols] = df[num_cols].fillna(0)

    # Drop zero-variance columns
    zero_var = [c for c in num_cols if df[c].std() == 0]
    df = df.drop(columns=zero_var)
    if zero_var:
        print(f"Dropped {len(zero_var)} zero-variance columns: {zero_var}")

    # Save
    df.to_csv(HERE / "features.csv", index=False, encoding="utf-8")

    print(f"\nFeature matrix: {df.shape[0]} artists x {df.shape[1]} columns")
    print(f"Seeds: {df['is_seed'].sum()}, Similar: {(df['is_seed']==0).sum()}")
    print(f"\nColumns:")
    for col in df.columns:
        nulls = df[col].isna().sum()
        print(f"  {col:<40} nulls={nulls}")
    print(f"\nSaved features.csv")


if __name__ == "__main__":
    main()
