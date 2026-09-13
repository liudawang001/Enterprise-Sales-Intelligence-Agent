"""Persist resumable research, delivery and export payloads.

Revision ID: 0009_fa001_durable_business_state
Revises: 0008_phase8_production_runtime
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_fa001_durable_business_state"
down_revision = "0008_phase8_production_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_runs",
        sa.Column("events_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column("delivery_snapshots", sa.Column("bundle_json", postgresql.JSONB()))
    op.add_column(
        "exports",
        sa.Column("events_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("exports", "events_json")
    op.drop_column("delivery_snapshots", "bundle_json")
    op.drop_column("research_runs", "events_json")
