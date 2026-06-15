import uuid
from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Artist(Base):
    __tablename__ = "artist"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    source_maps = relationship("ArtistSourceMap", back_populates="artist")
    observations = relationship("MetricObservation", back_populates="artist")
    lineup_slots = relationship("LineupSlot", back_populates="artist")
    validation_events = relationship("ValidationEvent", back_populates="artist")
    feedback = relationship("Feedback", back_populates="artist")


class ArtistSourceMap(Base):
    """Maps a canonical artist_id to per-source identifiers."""
    __tablename__ = "artist_source_map"
    __table_args__ = (UniqueConstraint("artist_id", "source"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artist_id = Column(UUID(as_uuid=True), ForeignKey("artist.id"), nullable=False)
    source = Column(String(50), nullable=False)   # chartmetric | ra | partyflock | lastfm | spotify
    external_id = Column(String(255))
    external_url = Column(Text)
    confidence = Column(Float, default=1.0)
    resolved_at = Column(DateTime, default=datetime.utcnow)

    artist = relationship("Artist", back_populates="source_maps")


class MetricObservation(Base):
    """Append-only time series. Converted to TimescaleDB hypertable in migration."""
    __tablename__ = "metric_observation"
    __table_args__ = (
        Index("ix_metric_obs_artist_metric", "artist_id", "source", "metric"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artist_id = Column(UUID(as_uuid=True), ForeignKey("artist.id"), nullable=False)
    source = Column(String(50), nullable=False)    # lastfm | partyflock | ra | chartmetric | scoring_engine
    metric = Column(String(100), nullable=False)
    value = Column(Float)
    observed_at = Column(DateTime, nullable=False)

    artist = relationship("Artist", back_populates="observations")


class Event(Base):
    __tablename__ = "event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500))
    date = Column(DateTime)
    venue = Column(String(255))
    city = Column(String(255))
    country = Column(String(10))
    capacity = Column(Integer)
    event_type = Column(String(50))    # club | festival
    source = Column(String(50))
    external_id = Column(String(255))
    external_url = Column(Text)

    lineup_slots = relationship("LineupSlot", back_populates="event")


class LineupSlot(Base):
    __tablename__ = "lineup_slot"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("event.id"), nullable=False)
    artist_id = Column(UUID(as_uuid=True), ForeignKey("artist.id"), nullable=False)
    billing_position = Column(Integer)   # 1 = headliner
    set_type = Column(String(50))        # dj | live | b2b

    event = relationship("Event", back_populates="lineup_slots")
    artist = relationship("Artist", back_populates="lineup_slots")


class ValidationEvent(Base):
    """Named career milestones — auto-detected or manually entered."""
    __tablename__ = "validation_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artist_id = Column(UUID(as_uuid=True), ForeignKey("artist.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    # event_type values: boiler_room | ra_podcast | bbc_r1 | ibiza_booking | circoloco |
    #   music_on | ants | piv | beatport_top10 | beatport_no1 | agency_signing |
    #   headline_500 | headline_1000 | headline_2000 | headline_5000 |
    #   extended_set | all_night | all_day | major_residency | tier_a_support | tier_a_b2b
    occurred_at = Column(DateTime, nullable=False)
    source = Column(String(20), default="auto")  # auto | manual
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    artist = relationship("Artist", back_populates="validation_events")


class Feedback(Base):
    """Booking-team input — stored as-is, never overwrites model output."""
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artist_id = Column(UUID(as_uuid=True), ForeignKey("artist.id"), nullable=False)
    user_id = Column(String(255))
    category = Column(String(100))
    # category values: fits_lofi | doesnt_fit | sound_to_develop | saturated |
    #   support_act | potential_headliner
    notes = Column(Text)
    score_delta = Column(JSONB)   # {"momentum": +5, "future_potential": -10}
    created_at = Column(DateTime, default=datetime.utcnow)

    artist = relationship("Artist", back_populates="feedback")


class SoundFramework(Base):
    __tablename__ = "sound_framework"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    genre = Column(String(100))

    festivals = relationship("FrameworkFestival", back_populates="framework")
    labels = relationship("FrameworkLabel", back_populates="framework")
    agencies = relationship("FrameworkAgency", back_populates="framework")
    artists = relationship("FrameworkArtist", back_populates="framework")
    media = relationship("FrameworkMedia", back_populates="framework")


class FrameworkFestival(Base):
    __tablename__ = "framework_festival"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    framework_id = Column(UUID(as_uuid=True), ForeignKey("sound_framework.id"), nullable=False)
    festival_name = Column(String(255), nullable=False)
    tier = Column(String(10))

    framework = relationship("SoundFramework", back_populates="festivals")


class FrameworkLabel(Base):
    __tablename__ = "framework_label"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    framework_id = Column(UUID(as_uuid=True), ForeignKey("sound_framework.id"), nullable=False)
    label_name = Column(String(255), nullable=False)
    tier = Column(String(10))

    framework = relationship("SoundFramework", back_populates="labels")


class FrameworkAgency(Base):
    __tablename__ = "framework_agency"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    framework_id = Column(UUID(as_uuid=True), ForeignKey("sound_framework.id"), nullable=False)
    agency_name = Column(String(255), nullable=False)
    tier = Column(String(10))   # A+ | A | B
    score = Column(Integer)     # 10 | 8 | 6

    framework = relationship("SoundFramework", back_populates="agencies")


class FrameworkArtist(Base):
    __tablename__ = "framework_artist"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    framework_id = Column(UUID(as_uuid=True), ForeignKey("sound_framework.id"), nullable=False)
    artist_id = Column(UUID(as_uuid=True), ForeignKey("artist.id"), nullable=False)
    tier = Column(String(10))   # A+ | A | B

    framework = relationship("SoundFramework", back_populates="artists")
    artist = relationship("Artist")


class FrameworkMedia(Base):
    __tablename__ = "framework_media"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    framework_id = Column(UUID(as_uuid=True), ForeignKey("sound_framework.id"), nullable=False)
    outlet_name = Column(String(255), nullable=False)
    tier = Column(Integer)   # 1 | 2 | 3

    framework = relationship("SoundFramework", back_populates="media")


class ResolutionQueue(Base):
    """Artists that couldn't be auto-resolved — await human review."""
    __tablename__ = "resolution_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False)
    external_id = Column(String(255))
    external_name = Column(String(255), nullable=False)
    candidates = Column(JSONB)   # [{artist_id, score, name}, ...]
    status = Column(String(20), default="pending")   # pending | resolved | rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)
    resolved_artist_id = Column(UUID(as_uuid=True), ForeignKey("artist.id"))
