"""Add Phase 6 versioned task control and execution lineage.

Revision ID: 0006_phase6_task_control
Revises: 0005_phase5_entity_evidence_scoring
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_phase6_task_control"
down_revision = "0005_phase5_entity_evidence_scoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("lead_tasks", sa.Column("id", sa.UUID(), primary_key=True), sa.Column("thread_id", sa.String(255), nullable=False, index=True), sa.Column("business_code", sa.String(80)), sa.Column("active_version", sa.Integer(), nullable=False), sa.Column("stage", sa.String(40), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("lead_task_versions", sa.Column("id", sa.UUID(), primary_key=True), sa.Column("task_id", sa.UUID(), sa.ForeignKey("lead_tasks.id", ondelete="CASCADE"), nullable=False, index=True), sa.Column("version", sa.Integer(), nullable=False), sa.Column("parent_version", sa.Integer()), sa.Column("business_code", sa.String(80)), sa.Column("region", sa.String(120)), sa.Column("target_count", sa.Integer()), sa.Column("constraints_json", postgresql.JSONB(), nullable=False), sa.Column("required_fields", postgresql.JSONB(), nullable=False), sa.Column("export_fields", postgresql.JSONB(), nullable=False), sa.Column("source_message_id", sa.String(255)), sa.Column("mutation_id", sa.UUID()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("task_id", "version"))
    op.create_table("task_reexecution_plans", sa.Column("id", sa.UUID(), primary_key=True), sa.Column("task_id", sa.UUID(), sa.ForeignKey("lead_tasks.id", ondelete="CASCADE"), nullable=False, index=True), sa.Column("base_version", sa.Integer(), nullable=False), sa.Column("target_version", sa.Integer(), nullable=False), sa.Column("original_scope", sa.String(40), nullable=False), sa.Column("final_scope", sa.String(40), nullable=False), sa.Column("start_stage", sa.String(40), nullable=False), sa.Column("steps_json", postgresql.JSONB(), nullable=False), sa.Column("reused_artifact_ids", postgresql.JSONB(), nullable=False), sa.Column("invalidated_artifact_ids", postgresql.JSONB(), nullable=False), sa.Column("required_fields", postgresql.JSONB(), nullable=False), sa.Column("reason_codes", postgresql.JSONB(), nullable=False), sa.Column("reuse_decisions", postgresql.JSONB(), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("escalation_reason", sa.Text()), sa.Column("estimated_external_calls", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)))
    op.create_table("task_mutations", sa.Column("id", sa.UUID(), primary_key=True), sa.Column("task_id", sa.UUID(), sa.ForeignKey("lead_tasks.id", ondelete="CASCADE"), nullable=False, index=True), sa.Column("base_version", sa.Integer(), nullable=False), sa.Column("target_version", sa.Integer()), sa.Column("source_message_id", sa.String(255), nullable=False), sa.Column("patch_json", postgresql.JSONB(), nullable=False), sa.Column("preview_json", postgresql.JSONB()), sa.Column("task_diff_json", postgresql.JSONB()), sa.Column("criteria_diff_json", postgresql.JSONB()), sa.Column("scope", sa.String(40)), sa.Column("reexecution_plan_id", sa.UUID()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("task_id", "source_message_id"))
    op.create_table("task_execution_snapshots", sa.Column("id", sa.UUID(), primary_key=True), sa.Column("task_id", sa.UUID(), sa.ForeignKey("lead_tasks.id", ondelete="CASCADE"), nullable=False, index=True), sa.Column("task_version", sa.Integer(), nullable=False), sa.Column("criteria_snapshot_id", sa.UUID()), sa.Column("search_plan_id", sa.UUID()), sa.Column("raw_candidate_set_id", sa.UUID()), sa.Column("filtered_candidate_set_id", sa.UUID()), sa.Column("researched_candidate_set_id", sa.UUID()), sa.Column("verified_lead_set_id", sa.UUID()), sa.Column("scoring_profile_id", sa.UUID()), sa.Column("lead_score_set_id", sa.UUID()), sa.Column("is_current", sa.Boolean(), nullable=False), sa.Column("validity", sa.String(24), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("task_id", "task_version"))
    op.add_column("lead_criteria_snapshots", sa.Column("artifact_validity", sa.String(24), nullable=False, server_default="REUSABLE"))
    for table in ("research_search_plans", "research_runs", "entity_resolution_runs", "verification_runs", "lead_scores", "verified_lead_sets"):
        op.add_column(table, sa.Column("task_version", sa.Integer()))
        op.add_column(table, sa.Column("artifact_validity", sa.String(24), nullable=False, server_default="REUSABLE"))


def downgrade() -> None:
    op.drop_column("lead_criteria_snapshots", "artifact_validity")
    for table in ("verified_lead_sets", "lead_scores", "verification_runs", "entity_resolution_runs", "research_runs", "research_search_plans"):
        op.drop_column(table, "artifact_validity")
        op.drop_column(table, "task_version")
    for table in ("task_execution_snapshots", "task_mutations", "task_reexecution_plans", "lead_task_versions", "lead_tasks"):
        op.drop_table(table)
