"""
Entity resolution: map a (source, name/external_id) to a canonical artist_id.

Resolution order:
  1. Exact match on external_id in artist_source_map
  2. Exact match on normalized name in artist table
  3. Fuzzy match on normalized name (rapidfuzz, threshold from config)
  4. Unresolved → resolution_queue for human review

Returns (artist_id, confidence) or (None, 0.0) if unresolved.
"""

import uuid
from datetime import datetime
from typing import Optional

from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from config import RESOLUTION_CONFIDENCE_THRESHOLD
from resolution.normalize import normalize
from schema.models import Artist, ArtistSourceMap, ResolutionQueue


def resolve(
    session: Session,
    name: str,
    source: str,
    external_id: Optional[str] = None,
    external_url: Optional[str] = None,
    auto_create: bool = False,
) -> tuple[Optional[uuid.UUID], float]:
    """
    Returns (artist_id, confidence). Confidence 1.0 = certain, <1.0 = fuzzy.
    If unresolved and auto_create=False: adds to resolution_queue and returns (None, 0.0).
    If auto_create=True: creates a new artist record and returns (new_id, 1.0).
    """
    # 1. Exact external_id match
    if external_id:
        mapping = (
            session.query(ArtistSourceMap)
            .filter_by(source=source, external_id=external_id)
            .first()
        )
        if mapping:
            return mapping.artist_id, 1.0

    norm = normalize(name)

    # 2. Exact normalized-name match
    artists = session.query(Artist).all()
    for a in artists:
        if normalize(a.name) == norm:
            _ensure_source_map(session, a.id, source, external_id, external_url, 1.0)
            return a.id, 1.0

    # 3. Fuzzy match
    if artists:
        choices = {str(a.id): normalize(a.name) for a in artists}
        result = process.extractOne(norm, choices, scorer=fuzz.token_sort_ratio)
        if result and result[1] >= RESOLUTION_CONFIDENCE_THRESHOLD * 100:
            artist_id = uuid.UUID(result[2])
            confidence = round(result[1] / 100, 3)
            _ensure_source_map(session, artist_id, source, external_id, external_url, confidence)
            return artist_id, confidence

    # 4. Unresolved
    if auto_create:
        artist = Artist(name=name)
        session.add(artist)
        session.flush()
        _ensure_source_map(session, artist.id, source, external_id, external_url, 1.0)
        return artist.id, 1.0

    _queue_unresolved(session, name, source, external_id, artists)
    return None, 0.0


def _ensure_source_map(
    session: Session,
    artist_id: uuid.UUID,
    source: str,
    external_id: Optional[str],
    external_url: Optional[str],
    confidence: float,
):
    existing = (
        session.query(ArtistSourceMap)
        .filter_by(artist_id=artist_id, source=source)
        .first()
    )
    if not existing:
        session.add(ArtistSourceMap(
            artist_id=artist_id,
            source=source,
            external_id=external_id,
            external_url=external_url,
            confidence=confidence,
            resolved_at=datetime.utcnow(),
        ))


def _queue_unresolved(
    session: Session,
    name: str,
    source: str,
    external_id: Optional[str],
    all_artists: list,
):
    norm = normalize(name)
    candidates = []
    if all_artists:
        choices = {str(a.id): normalize(a.name) for a in all_artists}
        results = process.extract(norm, choices, scorer=fuzz.token_sort_ratio, limit=5)
        candidates = [
            {"artist_id": r[2], "score": round(r[1] / 100, 3), "name": r[0]}
            for r in results
        ]

    existing = (
        session.query(ResolutionQueue)
        .filter_by(source=source, external_name=name, status="pending")
        .first()
    )
    if not existing:
        session.add(ResolutionQueue(
            source=source,
            external_id=external_id,
            external_name=name,
            candidates=candidates,
        ))
