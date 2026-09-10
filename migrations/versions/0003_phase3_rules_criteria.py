"""Add Phase 3 business rules, marketing rules and criteria snapshots.

Revision ID: 0003_phase3_rules_criteria
Revises: 0002_knowledge_tables
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_phase3_rules_criteria"
down_revision = "0002_knowledge_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("business_catalog", sa.Column("code", sa.String(80), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("aliases", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("business_rules", sa.Column("id", sa.UUID(), primary_key=True), sa.Column("business_code", sa.String(80), nullable=False, index=True), sa.Column("field", sa.String(120), nullable=False), sa.Column("operator", sa.String(20), nullable=False), sa.Column("value", sa.dialects.postgresql.JSONB(), nullable=False), sa.Column("value_type", sa.String(30), nullable=False), sa.Column("source_type", sa.String(40), nullable=False), sa.Column("constraint_type", sa.String(20), nullable=False), sa.Column("modality", sa.String(30)), sa.Column("weight", sa.Numeric()), sa.Column("confidence", sa.Numeric(), nullable=False), sa.Column("rationale", sa.Text()), sa.Column("region", sa.String(80)), sa.Column("effective_from", sa.Date()), sa.Column("effective_to", sa.Date()), sa.Column("status", sa.String(20), nullable=False), sa.Column("source_key", sa.String(255), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("business_rule_evidence", sa.Column("id", sa.UUID(), primary_key=True), sa.Column("rule_id", sa.UUID(), sa.ForeignKey("business_rules.id", ondelete="CASCADE"), nullable=False), sa.Column("document_id", sa.UUID(), nullable=False), sa.Column("chunk_id", sa.UUID(), nullable=False), sa.Column("page_start", sa.Integer()), sa.Column("page_end", sa.Integer()), sa.Column("excerpt", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("business_marketing_rules", sa.Column("id", sa.UUID(), primary_key=True), sa.Column("business_code", sa.String(80), nullable=False, index=True), sa.Column("field", sa.String(120), nullable=False), sa.Column("operator", sa.String(20), nullable=False), sa.Column("value", sa.dialects.postgresql.JSONB(), nullable=False), sa.Column("value_type", sa.String(30), nullable=False), sa.Column("constraint_type", sa.String(20), nullable=False), sa.Column("weight", sa.Numeric()), sa.Column("region", sa.String(80)), sa.Column("effective_from", sa.Date()), sa.Column("effective_to", sa.Date()), sa.Column("rationale", sa.Text()), sa.Column("status", sa.String(20), nullable=False), sa.Column("source_key", sa.String(255), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("lead_criteria_snapshots", sa.Column("id", sa.UUID(), primary_key=True), sa.Column("task_id", sa.String(80), nullable=False, index=True), sa.Column("task_version", sa.Integer(), nullable=False), sa.Column("business_code", sa.String(80), nullable=False), sa.Column("region_scope", sa.dialects.postgresql.JSONB(), nullable=False), sa.Column("target_count", sa.Integer(), nullable=False), sa.Column("hard_constraints", sa.dialects.postgresql.JSONB(), nullable=False), sa.Column("soft_constraints", sa.dialects.postgresql.JSONB(), nullable=False), sa.Column("required_fields", sa.dialects.postgresql.JSONB(), nullable=False), sa.Column("ranking_preferences", sa.dialects.postgresql.JSONB(), nullable=False), sa.Column("source_rule_ids", sa.dialects.postgresql.JSONB(), nullable=False), sa.Column("warnings", sa.dialects.postgresql.JSONB(), nullable=False), sa.Column("criteria_hash", sa.String(64), nullable=False, index=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))


def downgrade() -> None:
    op.drop_table("lead_criteria_snapshots")
    op.drop_table("business_marketing_rules")
    op.drop_table("business_rule_evidence")
    op.drop_table("business_rules")
    op.drop_table("business_catalog")

