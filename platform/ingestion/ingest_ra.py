"""
Ingest RA EventItem.jsonl and EventLineupItem.jsonl into canonical schema.

Usage:
    python -m ingestion.ingest_ra
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

RAW_DIR = Path(__file__).parent / "raw" / "ra"
RAW_DIR.mkdir(parents=True, exist_ok=True)


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


def main():
    events_path = SCRAPER_DATA_DIR / "EventItem.jsonl"
    lineups_path = SCRAPER_DATA_DIR / "EventLineupItem.jsonl"

    for path in [events_path, lineups_path]:
        if path.exists():
            dest = RAW_DIR / f"{path.stem}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.jsonl.gz"
            with path.open("rb") as f_in, gzip.open(dest, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

    event_rows = _load_jsonl(events_path)
    lineup_rows = _load_jsonl(lineups_path)
    print(f"Loaded {len(event_rows)} RA events, {len(lineup_rows)} lineup records")

    # Build lineup lookup: event_id → [artist, ...]
    lineup_by_event: dict[str, list[str]] = {}
    for r in lineup_rows:
        eid = r.get("event_id") or r.get("id")
        lineup = r.get("lineup") or []
        if eid and lineup:
            lineup_by_event[eid] = lineup

    skipped = ingested = 0

    with get_session() as session:
        for r in event_rows:
            artist_name = (r.get("artist") or "").strip()
            if not artist_name:
                continue

            artist_id, _ = resolve(session, artist_name, source="ra",
                                    external_id=r.get("artist_id") or r.get("ra_artist_id"))
            if not artist_id:
                skipped += 1
                continue

            external_id = r.get("id") or r.get("event_url")
            existing_event = (
                session.query(Event).filter_by(source="ra", external_id=external_id).first()
                if external_id else None
            )

            if not existing_event:
                date = None
                for field in ("date", "start_date", "startDate"):
                    if r.get(field):
                        try:
                            date = datetime.fromisoformat(str(r[field])[:19])
                            break
                        except Exception:
                            pass

                event = Event(
                    name=r.get("title") or r.get("event_name"),
                    date=date,
                    venue=r.get("venue"),
                    city=r.get("city"),
                    country=r.get("country"),
                    source="ra",
                    external_id=external_id,
                    external_url=r.get("url") or r.get("event_url"),
                )
                session.add(event)
                session.flush()
            else:
                event = existing_event

            slot_exists = session.query(LineupSlot).filter_by(
                event_id=event.id, artist_id=artist_id
            ).first()
            if not slot_exists:
                session.add(LineupSlot(event_id=event.id, artist_id=artist_id))

            # Store attending count as a metric observation
            attending = r.get("attending") or r.get("attending_count")
            if attending is not None:
                observed_at = (
                    datetime.fromisoformat(r["scraped_at"])
                    if r.get("scraped_at") else datetime.utcnow()
                )
                session.add(MetricObservation(
                    artist_id=artist_id,
                    source="ra",
                    metric="ra_event_attending",
                    value=float(attending),
                    observed_at=observed_at,
                ))
            ingested += 1

    print(f"RA ingestion: {ingested} events ingested, {skipped} unresolved (queued)")


if __name__ == "__main__":
    main()
