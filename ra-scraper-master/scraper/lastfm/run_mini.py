"""
Mini run: fetch a fresh LastFM snapshot for a small list of artists.

Used to test that repeated runs build time-series data (growth charts).
Run from the scraper/ directory:
    python lastfm/run_mini.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lastfm_scraper import fetch_artist_info, append_snapshot, load_existing_snapshots, compute_features
from datetime import datetime, timezone
import time

ARTISTS = [
    "The Darkraver", "Benny Rodrigues", "Vince", "Bass-D", "Bart Skils",
    "De Sluwe Vos", "Joris Voorn", "Boris Werner", "Cinnaman", "Steve Rachmad",
    "Luuk van Dijk", "Elias Mazian", "Adam Beyer", "Dart", "Philou Louzolo",
    "Loco Dice", "Speedy J", "Richie Hawtin", "Pan-Pot", "Chris Stussy",
]

RATE_LIMIT_DELAY = 0.25


def main():
    existing = load_existing_snapshots()
    now = datetime.now(timezone.utc).isoformat()

    print(f"Fetching {len(ARTISTS)} artists for second snapshot...")
    found = 0
    for i, name in enumerate(ARTISTS, 1):
        info = fetch_artist_info(name)
        time.sleep(RATE_LIMIT_DELAY)
        if info is None:
            print(f"  {i}/{len(ARTISTS)} {name}: NOT FOUND")
            continue

        snapshot = {
            "name":              info["name"],
            "query_name":        name,
            "listeners":         info["listeners"],
            "playcount":         info["playcount"],
            "plays_per_listener": round(info["playcount"] / info["listeners"], 2) if info["listeners"] else 0,
            "tags":              info["tags"],
            "similar":           info["similar"],
            "pf_fans":           0,
            "pf_past":           0,
            "pf_upcoming":       0,
            "pf_genres":         [],
            "scraped_at":        now,
            "is_mainstream":     info["listeners"] > 1_500_000,
        }
        append_snapshot(snapshot)
        history = existing.get(info["name"].lower(), []) + [snapshot]
        prev_count = len(existing.get(info["name"].lower(), []))
        delta = ""
        if prev_count >= 1:
            prev = existing[info["name"].lower()][-1]
            d = info["listeners"] - prev.get("listeners", 0)
            delta = f"  delta={d:+,}"
        print(f"  {i}/{len(ARTISTS)} {info['name']}: {info['listeners']:,} listeners  (snapshots now: {prev_count+1}){delta}")
        found += 1

    print(f"\nDone. {found}/{len(ARTISTS)} artists fetched. Run data_aggregator.py to rebuild enriched data.")


if __name__ == "__main__":
    main()
