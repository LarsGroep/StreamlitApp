"""
Parse LOFI event lineup data from lofi_events_raw.tsv.

Produces:
  lofi_booked_labels.csv  — artist, lofi_appearance_count, lofi_booked=1
  lofi_booked_artists.txt — unique artist names (sorted by appearance count)

Run:
    python parse_lofi_bookings.py
"""

import csv
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
SKIP = {
    "unnamed record", "",
    # Internal/billing placeholders in the DB
    "sellout", "hostingfee", "brandfee", "test joël", "karel",
    "sellout bonus marlon",
    # Descriptive tags that ended up in lineup fields
    "not a headliner",
    # Duplicate entries with role/format suffix
    "seconds (setaoc mass)", "seconds (phara)",
}


def clean_name(name: str) -> str:
    return name.strip().strip('"').strip()


def parse_lineup(s: str) -> list[str]:
    if not s:
        return []
    artists = []
    for part in s.split(","):
        name = clean_name(part)
        if name.lower() not in SKIP and name:
            artists.append(name)
    return artists


def main():
    tsv = HERE / "lofi_events_raw.tsv"
    counts: Counter = Counter()

    with tsv.open(encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)  # skip header
        for row in reader:
            if len(row) < 3:
                continue
            # Prefer DB column (index 3) — falls back to Lineup column (index 2)
            lineup_str = row[3].strip() if len(row) > 3 and row[3].strip() else row[2].strip()
            for artist in parse_lineup(lineup_str):
                counts[artist] += 1

    # Write CSV for ML feature integration
    labels_path = HERE / "lofi_booked_labels.csv"
    with labels_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["artist", "lofi_appearance_count", "lofi_booked"])
        for artist, count in counts.most_common():
            writer.writerow([artist, count, 1])

    # Write plain text list
    txt_path = HERE / "lofi_booked_artists.txt"
    with txt_path.open("w", encoding="utf-8") as f:
        for artist, _ in counts.most_common():
            f.write(artist + "\n")

    print(f"Unique LOFI artists: {len(counts)}")
    print(f"\nTop 30 by appearance count:")
    for artist, count in counts.most_common(30):
        print(f"  {count:3d}x  {artist}")
    print(f"\nSaved: {labels_path.name}, {txt_path.name}")


if __name__ == "__main__":
    main()
