"""
Ingest LastFMSnapshot.jsonl into metric_observation.
Keeps the most-recent snapshot per artist per day (idempotent on re-run).

Usage:
    python -m ingestion.ingest_lastfm
"""

import gzip
import json
import shutil
from datetime import datetime
from pathlib import Path

from schema.database import get_session
from schema.models import MetricObservation
from resolution.resolver import resolve
from config import SCRAPER_DATA_DIR

RAW_DIR = Path(__file__).parent / "raw" / "lastfm"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def main():
    path = SCRAPER_DATA_DIR / "lastfm" / "LastFMSnapshot.jsonl"
    if not path.exists():
        print(f"Not found: {path}")
        return

    dest = RAW_DIR / f"LastFMSnapshot_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.jsonl.gz"
    with path.open("rb") as f_in, gzip.open(dest, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    rows = _load_jsonl(path)
    print(f"Loaded {len(rows)} Last.fm snapshots")

    skipped = ingested = 0

    with get_session() as session:
        for r in rows:
            name = (r.get("name") or "").strip()
            if not name:
                continue

            artist_id, _ = resolve(session, name, source="lastfm")
            if not artist_id:
                skipped += 1
                continue

            observed_at_str = r.get("scraped_at") or r.get("observed_at")
            observed_at = (
                datetime.fromisoformat(observed_at_str)
                if observed_at_str else datetime.utcnow()
            )

            # Check idempotency: skip if we already have observations for this artist+day
            day_str = observed_at.strftime("%Y-%m-%d")
            existing = session.query(MetricObservation).filter(
                MetricObservation.artist_id == artist_id,
                MetricObservation.source == "lastfm",
                MetricObservation.metric == "lfm_listeners",
            ).filter(
                MetricObservation.observed_at.cast(str).like(f"{day_str}%")
            ).first()
            if existing:
                continue

            metrics = {
                "lfm_listeners": r.get("listeners"),
                "lfm_playcount": r.get("playcount"),
                "lfm_tag_count": len(r.get("tags") or []),
                "lfm_similar_count": len(r.get("similar") or []),
            }
            for metric, value in metrics.items():
                if value is not None:
                    session.add(MetricObservation(
                        artist_id=artist_id,
                        source="lastfm",
                        metric=metric,
                        value=float(value),
                        observed_at=observed_at,
                    ))
            ingested += 1

    print(f"Last.fm ingestion: {ingested} artists ingested, {skipped} unresolved (queued)")


if __name__ == "__main__":
    main()
