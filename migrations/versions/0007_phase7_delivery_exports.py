"""Add Phase 7 delivery snapshots and exports.

Revision ID: 0007_phase7_delivery_exports
Revises: 0006_phase6_task_control
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_phase7_delivery_exports"
down_revision = "0006_phase6_task_control"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_snapshots",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("task_id", sa.String(80), nullable=False, index=True),
        sa.Column("task_version", sa.Integer(), nullable=False),
        sa.Column("criteria_snapshot_id", sa.UUID()),
        sa.Column("verified_lead_set_id", sa.UUID(), nullable=False),
        sa.Column("lead_score_set_id", sa.UUID(), nullable=False),
        sa.Column("scoring_profile_id", sa.UUID()),
        sa.Column("execution_snapshot_id", sa.UUID()),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "task_id", "task_version", "execution_snapshot_id", name="uq_delivery_snapshot_execution"
        ),
    )
    op.create_table(
        "exports",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.UUID(),
            sa.ForeignKey("delivery_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("task_id", sa.String(80), nullable=False, index=True),
        sa.Column("task_version", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("fields_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("row_count", sa.Integer()),
        sa.Column("artifact_path", sa.Text()),
        sa.Column("file_name", sa.String(255)),
        sa.Column("file_size", sa.BigInteger()),
        sa.Column("sha256", sa.String(64)),
        sa.Column("request_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("exports")
    op.drop_table("delivery_snapshots")
