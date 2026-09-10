"""Create knowledge document and chunk tables.

Revision ID: 0002_knowledge_tables
Revises: 0001_enable_pgvector
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0002_knowledge_tables"
down_revision = "0001_enable_pgvector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("business", sa.String(120)),
        sa.Column("document_type", sa.String(80)),
        sa.Column("region", sa.String(80)),
        sa.Column("authority", sa.String(50), nullable=False),
        sa.Column("version", sa.String(80)),
        sa.Column("effective_from", sa.Date()),
        sa.Column("effective_to", sa.Date()),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_documents_business", "knowledge_documents", ["business"])
    op.create_index("ix_knowledge_documents_region", "knowledge_documents", ["region"])
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])
    op.create_index("ix_knowledge_documents_effective_from", "knowledge_documents", ["effective_from"])
    op.create_index("ix_knowledge_documents_effective_to", "knowledge_documents", ["effective_to"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("lexical_content", sa.Text(), nullable=False),
        sa.Column("search_vector", sa.dialects.postgresql.TSVECTOR()),
        sa.Column("embedding", Vector(1024)),
        sa.Column("chunk_type", sa.String(30), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("section_path", sa.Text()),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunk_document_index"),
        sa.UniqueConstraint("document_id", "content_hash", name="uq_knowledge_chunk_document_hash"),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_content_hash", "knowledge_chunks", ["content_hash"])
    op.create_index("ix_knowledge_chunks_search_vector", "knowledge_chunks", ["search_vector"], postgresql_using="gin")
    op.create_index(
        "ix_knowledge_chunks_embedding_hnsw",
        "knowledge_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_embedding_hnsw", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_search_vector", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_content_hash", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    for name in ["effective_to", "effective_from", "status", "region", "business"]:
        op.drop_index(f"ix_knowledge_documents_{name}", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
