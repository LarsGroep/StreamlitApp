"""
Last.fm time-series scraper for artist stats.

Each run appends a timestamped snapshot per artist to LastFMSnapshot.jsonl.
Over repeated runs this builds the time series needed to detect trending artists.
Also exports features.csv — a ready-to-use feature matrix for Isolation Forest training.

Usage:
    python lastfm_scraper.py
"""

import csv
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent   # scraper/lastfm/
ROOT = HERE.parent             # scraper/

API_KEY = "5a03e4d23e2fe689339fab0a79438f20"
BASE_URL = "https://ws.audioscrobbler.com/2.0/"

SNAPSHOT_FILE  = HERE / "LastFMSnapshot.jsonl"
FEATURES_FILE  = HERE / "features.csv"
ARTISTS_FILE   = ROOT / "artists.txt"
SIMILAR_FILE   = ROOT / "similar_artists.txt"
PF_ARTIST_FILE = ROOT / "PartyflockArtistItem.jsonl"

# Artists with more listeners than this are flagged as mainstream (not club-scale)
MAINSTREAM_THRESHOLD = 1_500_000

RATE_LIMIT_DELAY = 0.22   # ~4-5 req/s, well within Last.fm's 5 req/s limit


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _get(method: str, artist: str, **extra) -> dict | None:
    params = {
        "method": method,
        "artist": artist,
        "api_key": API_KEY,
        "format": "json",
        "autocorrect": "1",
        **extra,
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "LofiArtistScout/1.0 (lars.vandergroep@gmail.com)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        return None
    except Exception:
        return None


def fetch_similar_artists(name: str, limit: int = 50) -> list[str]:
    """Return up to `limit` similar artist names from Last.fm getSimilar endpoint.
    Returns more candidates than the 5 embedded in artist.getInfo."""
    data = _get("artist.getSimilar", name, limit=limit)
    if not data or "error" in data:
        return []
    return [a["name"] for a in (data.get("similarartists") or {}).get("artist") or []]


def fetch_tag_top_artists(tag: str, limit: int = 50) -> list[str]:
    """Return top artist names for a Last.fm genre tag (e.g. 'tech-house', 'minimal techno').
    Used to translate the LOFI Feel Matrix's top genre tags into discovery candidates."""
    params = {
        "method": "tag.getTopArtists",
        "tag": tag,
        "api_key": API_KEY,
        "format": "json",
        "limit": limit,
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "LofiArtistScout/1.0 (lars.vandergroep@gmail.com)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        if not data or "error" in data:
            return []
        return [a["name"] for a in (data.get("topartists") or {}).get("artist") or []]
    except Exception:
        return []


def fetch_artist_info(name: str) -> dict | None:
    data = _get("artist.getInfo", name)
    if not data or "error" in data:
        return None
    a = data.get("artist", {})
    stats = a.get("stats", {})
    tags = [t["name"].lower() for t in (a.get("tags") or {}).get("tag", [])]
    similar = [s["name"] for s in (a.get("similar") or {}).get("artist", [])]
    return {
        "name": a.get("name", name),
        "listeners": int(stats.get("listeners") or 0),
        "playcount": int(stats.get("playcount") or 0),
        "tags": tags,
        "similar": similar,
        "url": a.get("url"),
    }


# ---------------------------------------------------------------------------
# Artist list loading
# ---------------------------------------------------------------------------

def load_seed_artists() -> list[str]:
    return [
        l.strip() for l in ARTISTS_FILE.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.startswith("#")
    ]


def load_similar_artists() -> list[str]:
    if not SIMILAR_FILE.exists():
        return []
    names = []
    for line in SIMILAR_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name = line.split("|")[0].strip()
        if name:
            names.append(name)
    return names


def load_partyflock_stats() -> dict[str, dict]:
    """Return dict keyed by lowercase artist name with Partyflock stats."""
    if not PF_ARTIST_FILE.exists():
        return {}
    pf = {}
    for line in PF_ARTIST_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        key = (item.get("artist") or "").lower().strip()
        pf[key] = {
            "pf_fans": item.get("fans") or 0,
            "pf_past": item.get("past_performances") or 0,
            "pf_upcoming": item.get("upcoming_performances") or 0,
            "pf_genres": item.get("genres") or [],
        }
    return pf


# ---------------------------------------------------------------------------
# Snapshot persistence
# ---------------------------------------------------------------------------

def load_existing_snapshots() -> dict[str, list[dict]]:
    """Return dict: lower(name) -> list of snapshots sorted by time."""
    result: dict[str, list[dict]] = defaultdict(list)
    if not SNAPSHOT_FILE.exists():
        return result
    for line in SNAPSHOT_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            s = json.loads(line)
            result[s["name"].lower()].append(s)
        except Exception:
            pass
    return result


def append_snapshot(snapshot: dict):
    with open(SNAPSHOT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def compute_features(latest: dict, history: list[dict]) -> dict:
    listeners = latest["listeners"]
    playcount = latest["playcount"]
    ppl = round(playcount / listeners, 2) if listeners > 0 else 0.0
    log_listeners = round(math.log1p(listeners), 4)
    log_playcount = round(math.log1p(playcount), 4)

    features = {
        "listeners": listeners,
        "playcount": playcount,
        "plays_per_listener": ppl,
        "log_listeners": log_listeners,
        "log_playcount": log_playcount,
        "tag_count": len(latest.get("tags", [])),
        "similar_count": len(latest.get("similar", [])),
        "is_mainstream": int(listeners > MAINSTREAM_THRESHOLD),
    }

    # Partyflock features
    features["pf_fans"]     = latest.get("pf_fans", 0) or 0
    features["pf_past"]     = latest.get("pf_past", 0) or 0
    features["pf_upcoming"] = latest.get("pf_upcoming", 0) or 0

    # Time-delta features (require >= 2 snapshots)
    if len(history) >= 2:
        prev = sorted(history, key=lambda x: x["scraped_at"])[-2]
        prev_listeners = prev["listeners"]
        prev_playcount = prev["playcount"]

        listener_delta = listeners - prev_listeners
        playcount_delta = playcount - prev_playcount

        features["listener_delta"] = listener_delta
        features["playcount_delta"] = playcount_delta
        features["listener_growth_pct"] = round(
            listener_delta / prev_listeners * 100, 4
        ) if prev_listeners > 0 else 0.0
        features["playcount_growth_pct"] = round(
            playcount_delta / prev_playcount * 100, 4
        ) if prev_playcount > 0 else 0.0

        # Days between snapshots
        try:
            t1 = datetime.fromisoformat(prev["scraped_at"].replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(latest["scraped_at"].replace("Z", "+00:00"))
            days = max((t2 - t1).days, 1)
            features["listener_growth_per_day"] = round(listener_delta / days, 2)
            features["playcount_growth_per_day"] = round(playcount_delta / days, 2)
        except Exception:
            pass
    else:
        # No previous snapshot — deltas unavailable
        features["listener_delta"] = None
        features["playcount_delta"] = None
        features["listener_growth_pct"] = None
        features["playcount_growth_pct"] = None
        features["listener_growth_per_day"] = None
        features["playcount_growth_per_day"] = None

    return features


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    seeds = load_seed_artists()
    similar = load_similar_artists()
    all_names = list(dict.fromkeys(seeds + similar))  # deduplicated, order preserved
    pf_stats = load_partyflock_stats()
    existing = load_existing_snapshots()

    print(f"Artists to fetch: {len(all_names)} ({len(seeds)} seed + {len(similar)} similar)")
    print(f"Existing snapshots: {sum(len(v) for v in existing.values())} rows\n")

    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    mainstream: list[str] = []
    not_found: list[str] = []

    for i, name in enumerate(all_names, 1):
        info = fetch_artist_info(name)
        time.sleep(RATE_LIMIT_DELAY)

        if info is None:
            not_found.append(name)
            if i % 25 == 0:
                print(f"  {i}/{len(all_names)} ...")
            continue

        # Merge Partyflock stats
        pf = pf_stats.get(name.lower(), {})
        snapshot = {
            "name": info["name"],
            "query_name": name,
            "listeners": info["listeners"],
            "playcount": info["playcount"],
            "plays_per_listener": round(info["playcount"] / info["listeners"], 2) if info["listeners"] else 0,
            "tags": info["tags"],
            "similar": info["similar"],
            "pf_fans": pf.get("pf_fans", 0),
            "pf_past": pf.get("pf_past", 0),
            "pf_upcoming": pf.get("pf_upcoming", 0),
            "pf_genres": pf.get("pf_genres", []),
            "scraped_at": now,
            "is_mainstream": info["listeners"] > MAINSTREAM_THRESHOLD,
        }
        append_snapshot(snapshot)

        # Reload history including the snapshot we just wrote
        history = existing.get(info["name"].lower(), []) + [snapshot]
        features = compute_features(snapshot, history)
        features["name"] = info["name"]
        features["tags"] = ", ".join(info["tags"][:5])
        rows.append(features)

        if info["listeners"] > MAINSTREAM_THRESHOLD:
            mainstream.append(f"{info['name']} ({info['listeners']:,} listeners)")

        if i % 25 == 0:
            print(f"  {i}/{len(all_names)} fetched...")

    # --- Print summary table ---
    print(f"\n{'Artist':<35} {'Listeners':>10} {'Playcount':>12} {'PPL':>6}  {'Tags'}")
    print("-" * 90)
    club_rows = [r for r in rows if not r["is_mainstream"]]
    for r in sorted(club_rows, key=lambda x: -x["listeners"])[:60]:
        print(f"{r['name']:<35} {r['listeners']:>10,} {r['playcount']:>12,} {r['plays_per_listener']:>6.1f}  {r['tags']}")

    if mainstream:
        print(f"\n[!] Mainstream artists EXCLUDED from feature matrix ({len(mainstream)}):")
        for m in mainstream:
            print(f"   {m}")

    if not_found:
        print(f"\n   Not found on Last.fm ({len(not_found)}): {', '.join(not_found[:10])}")

    # --- Export feature matrix CSV ---
    training_rows = [r for r in rows if not r["is_mainstream"]]
    feature_cols = [
        "name", "listeners", "playcount", "plays_per_listener",
        "log_listeners", "log_playcount", "tag_count", "similar_count",
        "pf_fans", "pf_past", "pf_upcoming",
        "listener_delta", "playcount_delta",
        "listener_growth_pct", "playcount_growth_pct",
        "listener_growth_per_day", "playcount_growth_per_day",
        "tags",
    ]
    with open(FEATURES_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=feature_cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(training_rows)

    print(f"\nSnapshot appended to: {SNAPSHOT_FILE} ({len(rows)} artists)")
    print(f"Feature matrix:       {FEATURES_FILE} ({len(training_rows)} club-scale artists)")
    print(f"\nRun again weekly to build time-series deltas for Isolation Forest training.")


if __name__ == "__main__":
    main()
