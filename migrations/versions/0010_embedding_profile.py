"""Track the embedding profile used to build knowledge vectors."""

from alembic import op
import sqlalchemy as sa

revision = "0010_embedding_profile"
down_revision = "0009_fa001_durable_business_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_documents", sa.Column("embedding_provider", sa.String(40)))
    op.add_column("knowledge_documents", sa.Column("embedding_model", sa.String(120)))
    op.add_column("knowledge_documents", sa.Column("embedding_dimension", sa.Integer()))
    op.add_column("knowledge_documents", sa.Column("embedding_profile_version", sa.String(160)))
    op.create_index("ix_knowledge_documents_embedding_profile", "knowledge_documents", ["embedding_profile_version"])
    op.execute("UPDATE knowledge_chunks SET search_vector = to_tsvector('simple', lexical_content) WHERE search_vector IS NULL")


def downgrade() -> None:
    op.drop_index("ix_knowledge_documents_embedding_profile", table_name="knowledge_documents")
    for column in ("embedding_profile_version", "embedding_dimension", "embedding_model", "embedding_provider"):
        op.drop_column("knowledge_documents", column)
