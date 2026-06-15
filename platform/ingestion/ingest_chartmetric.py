"""
Ingest Chartmetric data for all tracked artists into metric_observation.

For each artist with a Chartmetric ID in artist_source_map:
  - Spotify listeners + followers (full time-series backfill)
  - Beatport chart positions
  - Instagram / TikTok / YouTube / SoundCloud social stats
  - Geo distribution (NL share, EU share, city count)
  - Playlist placements (count, editorial count, total reach)
  - Similar artists (written to sidecar JSONL for similarity model)

Run after seed_artists and entity resolution (requires CM IDs to be in artist_source_map).

Usage:
    python -m ingestion.ingest_chartmetric
    python -m ingestion.ingest_chartmetric --artist-name "Chris Stussy"   # single artist
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

import click
from sqlalchemy.orm import Session

from config import SCRAPER_DATA_DIR
from ingestion.chartmetric_client import ChartmetricClient
from resolution.resolver import resolve
from schema.database import get_session
from schema.models import Artist, ArtistSourceMap, MetricObservation

log = logging.getLogger(__name__)

SIMILAR_SIDECAR = SCRAPER_DATA_DIR / "similar_artists_cm.jsonl"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _cm_id(session: Session, artist_id: UUID) -> Optional[int]:
    row = (
        session.query(ArtistSourceMap)
        .filter_by(artist_id=artist_id, source="chartmetric")
        .first()
    )
    return int(row.external_id) if row and row.external_id else None


def _obs(session: Session, artist_id: UUID, metric: str, value: float, observed_at: datetime):
    session.add(MetricObservation(
        artist_id=artist_id,
        source="chartmetric",
        metric=metric,
        value=value,
        observed_at=observed_at,
    ))


def _already_ingested(session: Session, artist_id: UUID, metric: str, date_str: str) -> bool:
    """Skip if we already have this artist+metric for this date."""
    return session.query(MetricObservation).filter(
        MetricObservation.artist_id == artist_id,
        MetricObservation.source == "chartmetric",
        MetricObservation.metric == metric,
        MetricObservation.observed_at.cast("text").like(f"{date_str}%"),
    ).first() is not None


# ------------------------------------------------------------------
# Per-source ingestors
# ------------------------------------------------------------------

def ingest_spotify(session: Session, client: ChartmetricClient, artist_id: UUID, cm_id: int):
    rows = client.get_spotify_stats(cm_id)
    count = 0
    for r in rows:
        date_str = r.get("date", "")
        if not date_str:
            continue
        if _already_ingested(session, artist_id, "cm_sp_listeners", date_str[:10]):
            continue
        try:
            dt = datetime.fromisoformat(date_str)
        except ValueError:
            continue
        if r.get("listeners") is not None:
            _obs(session, artist_id, "cm_sp_listeners", float(r["listeners"]), dt)
        if r.get("followers") is not None:
            _obs(session, artist_id, "cm_sp_followers", float(r["followers"]), dt)
        if r.get("popularity") is not None:
            _obs(session, artist_id, "cm_sp_popularity", float(r["popularity"]), dt)
        count += 1
    log.debug("Spotify: %d new observations", count)


def ingest_social(session: Session, client: ChartmetricClient, artist_id: UUID, cm_id: int):
    platform_fields = {
        "instagram":  ["followers"],
        "tiktok":     ["followers", "likes"],
        "youtube":    ["subscribers", "views"],
        "soundcloud": ["followers"],
    }
    for platform, fields in platform_fields.items():
        try:
            rows = client.get_social_stats(cm_id, platform)
        except Exception as e:
            log.debug("Social %s skipped for cm_id=%d: %s", platform, cm_id, e)
            continue
        for r in rows:
            date_str = r.get("date", "")
            if not date_str:
                continue
            metric_key = f"cm_{platform}_{fields[0]}"
            if _already_ingested(session, artist_id, metric_key, date_str[:10]):
                continue
            try:
                dt = datetime.fromisoformat(date_str)
            except ValueError:
                continue
            for field in fields:
                if r.get(field) is not None:
                    _obs(session, artist_id, f"cm_{platform}_{field}", float(r[field]), dt)


def ingest_beatport(session: Session, client: ChartmetricClient, artist_id: UUID, cm_id: int):
    rows = client.get_beatport_charts(cm_id)
    for r in rows:
        date_str = r.get("chart_date") or r.get("date", "")
        if not date_str:
            continue
        try:
            dt = datetime.fromisoformat(date_str)
        except ValueError:
            continue
        if r.get("rank") is not None:
            _obs(session, artist_id, "cm_beatport_rank", float(r["rank"]), dt)
            # Also store inverse rank (higher = better chart position) for similarity features
            _obs(session, artist_id, "cm_beatport_inv_rank", 1.0 / float(r["rank"]), dt)


def ingest_geo(session: Session, client: ChartmetricClient, artist_id: UUID, cm_id: int):
    geo = client.get_geo_listeners(cm_id)
    cities = geo.get("cities") or []
    countries = geo.get("countries") or []
    now = datetime.utcnow()

    if not cities and not countries:
        return

    data = countries if countries else cities
    nl_total = sum(float(r.get("listeners", 0) or 0) for r in data if r.get("country_code") == "NL")
    eu_codes = {"DE", "NL", "BE", "FR", "ES", "IT", "PT", "AT", "CH", "PL", "CZ", "SE", "DK", "NO", "FI"}
    eu_total = sum(float(r.get("listeners", 0) or 0) for r in data if r.get("country_code") in eu_codes)
    grand_total = sum(float(r.get("listeners", 0) or 0) for r in data) or 1.0

    _obs(session, artist_id, "cm_geo_nl_share", nl_total / grand_total, now)
    _obs(session, artist_id, "cm_geo_eu_share", eu_total / grand_total, now)
    _obs(session, artist_id, "cm_geo_city_count", float(len(cities)), now)


def ingest_playlists(session: Session, client: ChartmetricClient, artist_id: UUID, cm_id: int):
    playlists = client.get_spotify_playlists(cm_id)
    now = datetime.utcnow()
    if not playlists:
        return
    editorial = [p for p in playlists if p.get("editorial")]
    total_reach = sum(float(p.get("followers", 0) or 0) for p in playlists)
    _obs(session, artist_id, "cm_sp_playlist_count", float(len(playlists)), now)
    _obs(session, artist_id, "cm_sp_editorial_count", float(len(editorial)), now)
    _obs(session, artist_id, "cm_sp_playlist_reach", total_reach, now)


def ingest_similar(session: Session, client: ChartmetricClient, artist_id: UUID, cm_id: int, artist_name: str):
    """Store similar artist names to a sidecar JSONL for the similarity model."""
    similars = client.get_similar_artists(cm_id)
    names = [s["name"] for s in similars if s.get("name")]
    if names:
        with SIMILAR_SIDECAR.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "artist_id": str(artist_id),
                "artist_name": artist_name,
                "cm_id": cm_id,
                "similar": names,
                "scraped_at": datetime.utcnow().isoformat(),
            }) + "\n")
    _obs(session, artist_id, "cm_similar_count", float(len(names)), datetime.utcnow())


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def _ingest_one(session: Session, client: ChartmetricClient, artist: Artist):
    cm_id = _cm_id(session, artist.id)
    if not cm_id:
        return False

    log.info("Ingesting CM data for %s (cm_id=%d)", artist.name, cm_id)
    try:
        ingest_spotify(session, client, artist.id, cm_id)
        ingest_social(session, client, artist.id, cm_id)
        ingest_beatport(session, client, artist.id, cm_id)
        ingest_geo(session, client, artist.id, cm_id)
        ingest_playlists(session, client, artist.id, cm_id)
        ingest_similar(session, client, artist.id, cm_id, artist.name)
        return True
    except Exception as e:
        log.error("Failed for %s: %s", artist.name, e)
        return False


@click.command()
@click.option("--artist-name", default=None, help="Ingest a single artist by name (partial match)")
def main(artist_name: Optional[str]):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    client = ChartmetricClient()

    with get_session() as session:
        if artist_name:
            artists = [
                a for a in session.query(Artist).all()
                if artist_name.lower() in a.name.lower()
            ]
        else:
            artists = session.query(Artist).all()

        total = len(artists)
        processed = skipped = 0

        for i, artist in enumerate(artists, 1):
            ok = _ingest_one(session, client, artist)
            if ok:
                processed += 1
            else:
                skipped += 1
            if i % 50 == 0:
                print(f"  Progress: {i}/{total}")

    print(f"\nChartmetric ingestion complete: {processed} ingested, {skipped} skipped (no CM ID)")


if __name__ == "__main__":
    main()
