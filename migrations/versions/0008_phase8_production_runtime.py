"""Add Phase 8 production runtime coordination and workspace scope.

Revision ID: 0008_phase8_production_runtime
Revises: 0007_phase7_delivery_exports
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_phase8_production_runtime"
down_revision = "0007_phase7_delivery_exports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lead_tasks", sa.Column("workspace_id", sa.String(120), nullable=False, server_default="local"))
    op.add_column("exports", sa.Column("workspace_id", sa.String(120), nullable=False, server_default="local"))
    op.add_column(
        "knowledge_documents", sa.Column("access_scope", sa.String(24), nullable=False, server_default="GLOBAL")
    )
    op.add_column("knowledge_documents", sa.Column("workspace_id", sa.String(120)))
    op.create_index("ix_knowledge_documents_scope_workspace", "knowledge_documents", ["access_scope", "workspace_id"])
    op.add_column("tool_runs", sa.Column("trace_id", sa.String(64)))
    op.add_column("tool_runs", sa.Column("run_id", postgresql.UUID(as_uuid=True)))
    op.add_column("tool_runs", sa.Column("fence_token", sa.BigInteger()))
    op.add_column("tool_runs", sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("tool_runs", sa.Column("rate_limit_wait_ms", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tool_runs", sa.Column("provider_latency_ms", sa.Integer()))

    op.create_table(
        "execution_runs",
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("request_id", sa.String(255), nullable=False),
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("workspace_id", sa.String(120), nullable=False),
        sa.Column("user_id", sa.String(120), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True)),
        sa.Column("task_version", sa.Integer()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("lease_owner", sa.String(255)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("fence_token", sa.BigInteger(), sa.Identity(), nullable=False, unique=True),
        sa.Column("trace_id", sa.String(64)),
        sa.Column("response_json", postgresql.JSONB()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("workspace_id", "request_id", name="uq_execution_run_request"),
    )
    op.create_index("ix_execution_runs_thread_status", "execution_runs", ["workspace_id", "thread_id", "status"])
    op.create_index("ix_execution_runs_lease_expires", "execution_runs", ["lease_expires_at"])
    op.create_index(
        "uq_execution_runs_active_thread",
        "execution_runs",
        ["workspace_id", "thread_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('CLAIMED', 'RUNNING')"),
    )
    op.create_table(
        "task_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lead_tasks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("workspace_id", sa.String(120), nullable=False),
        sa.Column("task_version", sa.Integer(), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("stage", sa.String(80)),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_task_events_task_created", "task_events", ["task_id", "created_at"])
    op.create_index("ix_lead_tasks_workspace_updated", "lead_tasks", ["workspace_id", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_lead_tasks_workspace_updated", table_name="lead_tasks")
    op.drop_table("task_events")
    op.drop_table("execution_runs")
    for column in ("provider_latency_ms", "rate_limit_wait_ms", "cache_hit", "fence_token", "run_id", "trace_id"):
        op.drop_column("tool_runs", column)
    op.drop_column("exports", "workspace_id")
    op.drop_column("lead_tasks", "workspace_id")
    op.drop_index("ix_knowledge_documents_scope_workspace", table_name="knowledge_documents")
    op.drop_column("knowledge_documents", "workspace_id")
    op.drop_column("knowledge_documents", "access_scope")
