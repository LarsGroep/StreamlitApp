"""
Auto-detect validation events from event/lineup data.
Manual entry is handled via the feedback UI (Phase 4).

Auto-detectable:
  - ibiza_booking: event in Ibiza city
  - circoloco / music_on / ants / piv: event name contains festival name
  - headline_500 / headline_1000 / headline_2000 / headline_5000: billing_position=1 + capacity
  - tier_a_support: billing_position > 1 at event where a Tier A artist headlines

Usage:
    python -m scoring.validation_events
"""

from datetime import datetime

from sqlalchemy.orm import Session

from schema.database import get_session
from schema.models import (
    Artist, Event, FrameworkArtist, LineupSlot,
    SoundFramework, ValidationEvent,
)

IBIZA_ALIASES = {"ibiza", "eivissa", "sant rafel", "sant jordi"}

FESTIVAL_EVENT_TYPES = {
    "circoloco": "circoloco",
    "music on": "music_on",
    "ants": "ants",
    "piv": "piv",
    "paradise": "paradise",
}

CAPACITY_MILESTONES = [
    (5000, "headline_5000"),
    (2000, "headline_2000"),
    (1000, "headline_1000"),
    (500,  "headline_500"),
]


def _add_if_new(session: Session, artist_id, event_type: str, occurred_at: datetime, source: str = "auto"):
    exists = session.query(ValidationEvent).filter_by(
        artist_id=artist_id, event_type=event_type
    ).first()
    if not exists:
        session.add(ValidationEvent(
            artist_id=artist_id,
            event_type=event_type,
            occurred_at=occurred_at,
            source=source,
        ))
        return True
    return False


def detect_all():
    with get_session() as session:
        framework = session.query(SoundFramework).filter_by(name="tech_house").first()
        tier_a_artist_ids = set()
        if framework:
            tier_a_artist_ids = {
                fa.artist_id
                for fa in session.query(FrameworkArtist).filter_by(framework_id=framework.id).all()
                if fa.tier in ("A", "A+")
            }

        artists = session.query(Artist).all()
        total_new = 0

        for artist in artists:
            slots = (
                session.query(LineupSlot)
                .filter_by(artist_id=artist.id)
                .join(LineupSlot.event)
                .all()
            )

            for slot in slots:
                event: Event = slot.event
                if not event or not event.date:
                    continue

                event_name_lower = (event.name or "").lower()
                city_lower = (event.city or "").lower()

                # Ibiza booking
                if city_lower in IBIZA_ALIASES:
                    if _add_if_new(session, artist.id, "ibiza_booking", event.date):
                        total_new += 1

                # Named festival bookings
                for keyword, event_type in FESTIVAL_EVENT_TYPES.items():
                    if keyword in event_name_lower:
                        if _add_if_new(session, artist.id, event_type, event.date):
                            total_new += 1

                # Capacity milestones (headliner only)
                if slot.billing_position == 1 and event.capacity:
                    for cap, vtype in CAPACITY_MILESTONES:
                        if event.capacity >= cap:
                            if _add_if_new(session, artist.id, vtype, event.date):
                                total_new += 1
                            break  # only the highest applicable milestone

                # Tier A support slot
                if slot.billing_position and slot.billing_position > 1 and tier_a_artist_ids:
                    headliner_slots = session.query(LineupSlot).filter_by(
                        event_id=event.id, billing_position=1
                    ).all()
                    for h in headliner_slots:
                        if h.artist_id in tier_a_artist_ids:
                            if _add_if_new(session, artist.id, "tier_a_support", event.date):
                                total_new += 1
                            break

        print(f"Validation event detection: {total_new} new milestones recorded.")


if __name__ == "__main__":
    detect_all()
