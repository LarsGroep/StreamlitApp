"""
Seed the artist table from artists.txt and lofi_booked_labels.csv.
Run once before any other ingestion.

Usage:
    python -m ingestion.seed_artists
"""

import csv
from datetime import datetime
from pathlib import Path

from schema.database import get_session, init_db
from schema.models import Artist, MetricObservation
from config import SCRAPER_DATA_DIR


def seed():
    init_db()

    artists_file = SCRAPER_DATA_DIR / "artists.txt"
    labels_file = SCRAPER_DATA_DIR / "lofi_booked_labels.csv"

    names: set[str] = set()

    # Seed list
    for line in artists_file.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if name and not name.startswith("#"):
            names.add(name)

    # LOFI booked artists (may add names not in seed list)
    lofi_labels: dict[str, dict] = {}
    if labels_file.exists():
        with labels_file.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                name = row["artist"].strip()
                if name:
                    names.add(name)
                    lofi_labels[name.lower()] = {
                        "lofi_booked": int(row["lofi_booked"]),
                        "lofi_appearance_count": int(row["lofi_appearance_count"]),
                    }

    with get_session() as session:
        existing_names = {a.name.lower() for a in session.query(Artist).all()}
        new_count = 0
        now = datetime.utcnow()

        for name in sorted(names):
            if name.lower() in existing_names:
                continue

            artist = Artist(name=name, created_at=now)
            session.add(artist)
            session.flush()
            new_count += 1

            # Record LOFI booking label as first metric observation
            label = lofi_labels.get(name.lower())
            if label:
                for metric, value in label.items():
                    session.add(MetricObservation(
                        artist_id=artist.id,
                        source="lofi_internal",
                        metric=metric,
                        value=float(value),
                        observed_at=now,
                    ))

    print(f"Seeded {new_count} new artists ({len(names)} total in source files).")


if __name__ == "__main__":
    seed()
