"""Phase 6 — LOFI internal ticket sales schema

Revision ID: 002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ticket_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("artist.id"), nullable=False),
        sa.Column("event_date", sa.DateTime, nullable=False),
        sa.Column("venue", sa.String(255)),
        sa.Column("city", sa.String(100)),
        sa.Column("capacity", sa.Integer),
        sa.Column("tickets_sold", sa.Integer),
        sa.Column("sell_out", sa.Boolean),
        sa.Column("revenue", sa.Float),
        sa.Column("source", sa.String(50), default="lofi_internal"),
        sa.Column("created_at", sa.DateTime),
    )
    # Convert to TimescaleDB hypertable for time-series queries
    op.execute("SELECT create_hypertable('ticket_event', 'event_date', if_not_exists => TRUE)")

    op.create_table(
        "audience_demographic",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ticket_event.id")),
        sa.Column("age_group", sa.String(20)),    # 18-24 | 25-34 | 35-44 | 45+
        sa.Column("gender", sa.String(20)),
        sa.Column("nationality", sa.String(10)),
        sa.Column("pct_of_audience", sa.Float),
    )


def downgrade():
    op.drop_table("audience_demographic")
    op.drop_table("ticket_event")
