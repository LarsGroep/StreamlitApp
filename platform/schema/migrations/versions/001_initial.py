"""Initial schema + TimescaleDB hypertable

Revision ID: 001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "artist",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "artist_source_map",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("artist.id"), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255)),
        sa.Column("external_url", sa.Text),
        sa.Column("confidence", sa.Float, default=1.0),
        sa.Column("resolved_at", sa.DateTime),
        sa.UniqueConstraint("artist_id", "source"),
    )

    op.create_table(
        "metric_observation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("artist.id"), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("value", sa.Float),
        sa.Column("observed_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_metric_obs_artist_metric", "metric_observation", ["artist_id", "source", "metric"])

    # Convert to TimescaleDB hypertable, partitioned by observed_at
    op.execute("SELECT create_hypertable('metric_observation', 'observed_at', if_not_exists => TRUE)")

    op.create_table(
        "event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(500)),
        sa.Column("date", sa.DateTime),
        sa.Column("venue", sa.String(255)),
        sa.Column("city", sa.String(255)),
        sa.Column("country", sa.String(10)),
        sa.Column("capacity", sa.Integer),
        sa.Column("event_type", sa.String(50)),
        sa.Column("source", sa.String(50)),
        sa.Column("external_id", sa.String(255)),
        sa.Column("external_url", sa.Text),
    )

    op.create_table(
        "lineup_slot",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("event.id"), nullable=False),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("artist.id"), nullable=False),
        sa.Column("billing_position", sa.Integer),
        sa.Column("set_type", sa.String(50)),
    )

    op.create_table(
        "validation_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("artist.id"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("occurred_at", sa.DateTime, nullable=False),
        sa.Column("source", sa.String(20), default="auto"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime),
    )

    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("artist.id"), nullable=False),
        sa.Column("user_id", sa.String(255)),
        sa.Column("category", sa.String(100)),
        sa.Column("notes", sa.Text),
        sa.Column("score_delta", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime),
    )

    op.create_table(
        "sound_framework",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("genre", sa.String(100)),
    )

    for table, fk_col, name_col, extra_cols in [
        ("framework_festival", None, "festival_name", [sa.Column("tier", sa.String(10))]),
        ("framework_label",    None, "label_name",    [sa.Column("tier", sa.String(10))]),
        ("framework_media",    None, "outlet_name",   [sa.Column("tier", sa.Integer)]),
    ]:
        op.create_table(
            table,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("framework_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sound_framework.id"), nullable=False),
            sa.Column(name_col, sa.String(255), nullable=False),
            *extra_cols,
        )

    op.create_table(
        "framework_agency",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("framework_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sound_framework.id"), nullable=False),
        sa.Column("agency_name", sa.String(255), nullable=False),
        sa.Column("tier", sa.String(10)),
        sa.Column("score", sa.Integer),
    )

    op.create_table(
        "framework_artist",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("framework_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sound_framework.id"), nullable=False),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("artist.id"), nullable=False),
        sa.Column("tier", sa.String(10)),
    )

    op.create_table(
        "resolution_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255)),
        sa.Column("external_name", sa.String(255), nullable=False),
        sa.Column("candidates", postgresql.JSONB),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("created_at", sa.DateTime),
        sa.Column("resolved_at", sa.DateTime),
        sa.Column("resolved_artist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("artist.id")),
    )


def downgrade():
    for t in [
        "resolution_queue", "framework_artist", "framework_agency",
        "framework_media", "framework_label", "framework_festival",
        "sound_framework", "feedback", "validation_event",
        "lineup_slot", "event", "metric_observation",
        "artist_source_map", "artist",
    ]:
        op.drop_table(t)
