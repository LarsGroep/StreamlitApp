"""
Ingest Partyflock JSONL data into the canonical schema.

Reads:
  - PartyflockArtistItem.jsonl  → metric_observation (fans, performances, etc.)
  - PartyflockEventItem.jsonl   → event + lineup_slot

Usage:
    python -m ingestion.ingest_partyflock
"""

import gzip
import json
import shutil
from datetime import datetime
from pathlib import Path

from schema.database import get_session
from schema.models import Event, LineupSlot, MetricObservation
from resolution.resolver import resolve
from config import SCRAPER_DATA_DIR

RAW_DIR = Path(__file__).parent / "raw" / "partyflock"
RAW_DIR.mkdir(parents=True, exist_ok=True)

VOTE_MAP = {"geweldig": 5, "goed": 4, "redelijk": 3, "matig": 2, "slecht": 1}


def _load_jsonl(path: Path) -> list[dict]:
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


def _archive_raw(src: Path):
    """Compress a snapshot of the raw file before processing."""
    dest = RAW_DIR / f"{src.stem}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.jsonl.gz"
    with src.open("rb") as f_in, gzip.open(dest, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)


def ingest_artist_profiles(session, rows: list[dict]):
    skipped = 0
    ingested = 0
    for r in rows:
        name = (r.get("artist") or "").strip()
        if not name:
            continue
        artist_id, _ = resolve(
            session, name, source="partyflock",
            external_id=r.get("partyflock_artist_id"),
            external_url=r.get("partyflock_url"),
        )
        if not artist_id:
            skipped += 1
            continue

        observed_at = datetime.fromisoformat(r["scraped_at"]) if r.get("scraped_at") else datetime.utcnow()

        metrics = {
            "pf_fans": r.get("fans"),
            "pf_past_performances": r.get("past_performances"),
            "pf_upcoming_performances": r.get("upcoming_performances"),
            "pf_photos": r.get("photos"),
            "pf_videos": r.get("videos"),
            "pf_vote_score": VOTE_MAP.get(r.get("vote_result"), None),
            "pf_total_performances": r.get("total_performances"),
        }

        for metric, value in metrics.items():
            if value is not None:
                session.add(MetricObservation(
                    artist_id=artist_id,
                    source="partyflock",
                    metric=metric,
                    value=float(value),
                    observed_at=observed_at,
                ))
        ingested += 1

    print(f"  Artist profiles: {ingested} ingested, {skipped} unresolved (queued)")


def ingest_events(session, rows: list[dict]):
    skipped = 0
    ingested = 0
    for r in rows:
        name = (r.get("artist") or "").strip()
        if not name:
            continue
        artist_id, _ = resolve(session, name, source="partyflock",
                                external_id=r.get("partyflock_artist_id"))
        if not artist_id:
            skipped += 1
            continue

        external_id = r.get("id") or r.get("event_url")
        existing = session.query(Event).filter_by(
            source="partyflock", external_id=external_id
        ).first() if external_id else None

        if not existing:
            date = None
            if r.get("start_date"):
                try:
                    date = datetime.fromisoformat(r["start_date"])
                except Exception:
                    pass

            event = Event(
                name=r.get("event_name"),
                date=date,
                venue=r.get("venue"),
                city=r.get("city"),
                country=r.get("country"),
                source="partyflock",
                external_id=external_id,
                external_url=r.get("event_url"),
            )
            session.add(event)
            session.flush()
        else:
            event = existing

        slot_exists = session.query(LineupSlot).filter_by(
            event_id=event.id, artist_id=artist_id
        ).first()
        if not slot_exists:
            session.add(LineupSlot(event_id=event.id, artist_id=artist_id))
        ingested += 1

    print(f"  Events: {ingested} ingested, {skipped} unresolved (queued)")


def main():
    artists_path = SCRAPER_DATA_DIR / "PartyflockArtistItem.jsonl"
    events_path = SCRAPER_DATA_DIR / "PartyflockEventItem.jsonl"

    for path in [artists_path, events_path]:
        if path.exists():
            _archive_raw(path)

    artist_rows = _load_jsonl(artists_path)
    event_rows = _load_jsonl(events_path)
    print(f"Loaded {len(artist_rows)} artist profiles, {len(event_rows)} events")

    with get_session() as session:
        ingest_artist_profiles(session, artist_rows)
        ingest_events(session, event_rows)

    print("Partyflock ingestion complete.")


if __name__ == "__main__":
    main()
