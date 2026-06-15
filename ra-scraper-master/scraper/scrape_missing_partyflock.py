"""
Compute which artists are missing from PartyflockArtistItem.jsonl and write
them to missing_artists.txt, then run the Partyflock spider for only those artists.

Usage:
    python scrape_missing_partyflock.py          # writes missing_artists.txt + runs spider
    python scrape_missing_partyflock.py --dry-run # just prints the missing list
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
ARTISTS_FILE = HERE / "artists.txt"
SCRAPED_FILE = HERE / "PartyflockArtistItem.jsonl"
MISSING_FILE = HERE / "missing_artists.txt"


def load_artists(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")]


def load_scraped_artists(path: Path) -> set[str]:
    if not path.exists():
        return set()
    scraped = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            name = json.loads(line).get("artist", "")
            if name:
                scraped.add(name.lower())
        except Exception:
            pass
    return scraped


def main():
    dry_run = "--dry-run" in sys.argv

    all_artists = load_artists(ARTISTS_FILE)
    scraped = load_scraped_artists(SCRAPED_FILE)

    missing = [a for a in all_artists if a.lower() not in scraped]

    print(f"Total in artists.txt:          {len(all_artists)}")
    print(f"Already scraped (JSONL):       {len(scraped)}")
    print(f"Missing (will scrape):         {len(missing)}")

    if not missing:
        print("Nothing to scrape — all artists are already in PartyflockArtistItem.jsonl.")
        return

    if dry_run:
        print("\nMissing artists:")
        for a in missing:
            print(f"  {a}")
        return

    MISSING_FILE.write_text("\n".join(missing), encoding="utf-8")
    print(f"\nWrote {len(missing)} artists to {MISSING_FILE.name}")
    print("Starting Partyflock spider for missing artists...\n")

    result = subprocess.run(
        [
            "scrapy", "crawl", "partyflock_spider",
            "-a", f"artists_file=missing_artists.txt",
        ],
        cwd=HERE,  # run from scraper/ so JSONL files land next to artists.txt
    )

    if result.returncode != 0:
        print(f"\nSpider exited with code {result.returncode}")
        sys.exit(result.returncode)

    # Clean up temp file
    MISSING_FILE.unlink(missing_ok=True)
    print("\nDone. Results appended to PartyflockArtistItem.jsonl and PartyflockEventItem.jsonl.")


if __name__ == "__main__":
    main()
