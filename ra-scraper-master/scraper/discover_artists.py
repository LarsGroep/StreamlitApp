"""
Derives similar artists from co-appearance data in PartyflockLineupItem.jsonl,
then filters candidates to techno-style genres by scraping their Partyflock profiles.

Run after partyflock_event_spider:
    python discover_artists.py
"""

import json
import re
import time
import urllib.request
import urllib.error
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent

LINEUP_FILE = HERE / "PartyflockLineupItem.jsonl"
ARTISTS_FILE = HERE / "artists.txt"
OUTPUT_FILE = HERE / "similar_artists.txt"

MIN_CO_APPEARANCES = 3      # minimum events co-appearing with any seed artist
MAX_PROFILE_LOOKUPS = 300   # cap on Partyflock profile fetches

TECHNO_GENRES = {
    "techno", "tech-house", "dark-techno", "hard-techno", "industrial-techno",
    "minimal", "minimal-techno", "acid-techno", "deep-tech", "electro",
    "house", "deep-house", "progressive-house", "tech-trance",
    "dub-techno", "ambient-techno", "modular", "noise",
}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def normalize(name: str) -> str:
    return name.strip().lower()


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def fetch_genres(artist_name: str) -> list[str] | None:
    """Fetch Partyflock profile and return genre list, or None on 404/error."""
    slug = _slug(artist_name)
    url = f"https://partyflock.nl/artist/{slug}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; lofi-research-bot/1.0)"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read().decode("utf-8", errors="replace")
        genres = re.findall(r'href="/agenda/genre/([^"]+)"', html)
        return list(dict.fromkeys(genres))  # deduplicated, order preserved
    except urllib.error.HTTPError:
        return None
    except Exception:
        return None


def is_techno_style(genres: list[str]) -> bool:
    if not genres:
        return False
    return bool(set(genres) & TECHNO_GENRES)


def main():
    if not LINEUP_FILE.exists():
        print("PartyflockLineupItem.jsonl not found — run partyflock_event_spider first")
        return

    seed_names = [
        line.strip()
        for line in ARTISTS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    seed_set = set(normalize(n) for n in seed_names)
    print(f"Seed artists: {len(seed_set)}")

    events = load_jsonl(LINEUP_FILE)
    print(f"Events with lineups: {len(events)}")

    co_count: Counter = Counter()
    co_with: defaultdict = defaultdict(Counter)

    for event in events:
        lineup = event.get("lineup") or []
        normalized = [normalize(a) for a in lineup]
        seeds_in_event = [a for a in normalized if a in seed_set]
        non_seeds = [a for a in normalized if a not in seed_set and a]

        if not seeds_in_event:
            continue

        for artist in non_seeds:
            co_count[artist] += 1
            for seed in seeds_in_event:
                co_with[artist][seed] += 1

    candidates_raw = [
        (artist, count, dict(co_with[artist].most_common(3)))
        for artist, count in co_count.most_common()
        if count >= MIN_CO_APPEARANCES
    ]
    print(f"\nCo-appearance candidates (>= {MIN_CO_APPEARANCES} events): {len(candidates_raw)}")

    # --- Genre filter ---
    print(f"\nFetching Partyflock profiles for top {min(MAX_PROFILE_LOOKUPS, len(candidates_raw))} candidates...")
    results = []
    for i, (artist, count, top_seeds) in enumerate(candidates_raw[:MAX_PROFILE_LOOKUPS]):
        genres = fetch_genres(artist)
        qualifies = is_techno_style(genres) if genres is not None else None
        results.append((artist, count, top_seeds, genres or [], qualifies))
        if (i + 1) % 25 == 0:
            found = sum(1 for _, _, _, _, q in results if q)
            print(f"  {i+1}/{min(MAX_PROFILE_LOOKUPS, len(candidates_raw))} fetched — {found} techno-style so far")
        time.sleep(0.15)  # polite rate limit

    # Separate: confirmed techno-style, unknown (404/no profile), non-techno
    techno = [(a, c, s, g) for a, c, s, g, q in results if q is True]
    unknown = [(a, c, s, g) for a, c, s, g, q in results if q is None]
    other = [(a, c, s, g) for a, c, s, g, q in results if q is False]

    print(f"\nResults:")
    print(f"  Techno-style confirmed: {len(techno)}")
    print(f"  No Partyflock profile:  {len(unknown)}")
    print(f"  Other genres:           {len(other)}")

    print(f"\n{'Artist':<35} {'Events':>6}  {'Genres':<45}  Top co-seed")
    print("-" * 100)
    for artist, count, top_seeds, genres in techno[:50]:
        top = ", ".join(f"{s}({n})" for s, n in list(top_seeds.items())[:2])
        print(f"{artist:<35} {count:>6}  {', '.join(genres):<45}  {top}")

    # Write full results
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"# Similar artists — techno-style confirmed, sorted by co-appearances\n")
        f.write(f"# Minimum co-appearances with seed artists: {MIN_CO_APPEARANCES}\n\n")
        f.write("# === TECHNO-STYLE CONFIRMED ===\n")
        for artist, count, top_seeds, genres in techno:
            top = ", ".join(f"{s}({n})" for s, n in top_seeds.items())
            f.write(f"{artist} | {count} | {', '.join(genres)} | {top}\n")
        f.write("\n# === NO PARTYFLOCK PROFILE (manual review) ===\n")
        for artist, count, top_seeds, _ in unknown[:50]:
            top = ", ".join(f"{s}({n})" for s, n in top_seeds.items())
            f.write(f"{artist} | {count} | unknown | {top}\n")

    print(f"\nSaved to {OUTPUT_FILE}")
    print("Copy confirmed artists into artists.txt, then re-run make build to scrape their full data.")


if __name__ == "__main__":
    main()
