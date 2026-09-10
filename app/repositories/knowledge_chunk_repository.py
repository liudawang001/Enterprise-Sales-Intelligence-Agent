from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.models import KnowledgeChunk
from app.persistence.models.chunk import KnowledgeChunkRecord


class KnowledgeChunkRepository:
    """Async PostgreSQL adapter for chunk content, vectors and citations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_for_document(self, document_id: UUID, chunks: list[KnowledgeChunk]) -> None:
        existing = (await self.session.scalars(select(KnowledgeChunkRecord).where(KnowledgeChunkRecord.document_id == document_id))).all()
        for record in existing:
            await self.session.delete(record)
        self.session.add_all([
            KnowledgeChunkRecord(
                id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                lexical_content=chunk.lexical_content,
                chunk_type=chunk.chunk_type.value,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section_path=chunk.section_path,
                content_hash=chunk.content_hash,
                embedding=chunk.embedding,
                metadata_json=chunk.metadata,
            )
            for chunk in chunks
        ])
        await self.session.flush()

    async def get(self, chunk_id: UUID) -> KnowledgeChunk | None:
        record = await self.session.get(KnowledgeChunkRecord, chunk_id)
        if not record:
            return None
        return KnowledgeChunk.model_validate({
            "id": record.id,
            "document_id": record.document_id,
            "chunk_index": record.chunk_index,
            "content": record.content,
            "lexical_content": record.lexical_content,
            "embedding": record.embedding,
            "chunk_type": record.chunk_type,
            "page_start": record.page_start,
            "page_end": record.page_end,
            "section_path": record.section_path,
            "content_hash": record.content_hash,
            "metadata": record.metadata_json,
        })
