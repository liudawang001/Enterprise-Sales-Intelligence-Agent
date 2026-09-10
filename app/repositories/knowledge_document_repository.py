from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.enums import DocumentStatus
from app.knowledge.models import KnowledgeDocument
from app.persistence.models.document import KnowledgeDocumentRecord


class KnowledgeDocumentRepository:
    """Async PostgreSQL adapter for knowledge document metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, document: KnowledgeDocument) -> KnowledgeDocument:
        record = KnowledgeDocumentRecord(**document.model_dump(exclude={"created_at", "updated_at"}))
        self.session.add(record)
        await self.session.flush()
        return document

    async def get(self, document_id: UUID) -> KnowledgeDocument | None:
        record = await self.session.get(KnowledgeDocumentRecord, document_id)
        return self._to_domain(record) if record else None

    async def find_by_hash(self, file_hash: str) -> KnowledgeDocument | None:
        result = await self.session.scalar(select(KnowledgeDocumentRecord).where(KnowledgeDocumentRecord.file_hash == file_hash))
        return self._to_domain(result) if result else None

    async def list(self) -> list[KnowledgeDocument]:
        records = (await self.session.scalars(select(KnowledgeDocumentRecord).order_by(KnowledgeDocumentRecord.created_at.desc()))).all()
        return [self._to_domain(record) for record in records]

    async def set_status(self, document_id: UUID, status: DocumentStatus, *, error_message: str | None = None) -> KnowledgeDocument | None:
        record = await self.session.get(KnowledgeDocumentRecord, document_id)
        if not record:
            return None
        record.status = status.value
        record.error_message = error_message
        await self.session.flush()
        return self._to_domain(record)

    @staticmethod
    def _to_domain(record: KnowledgeDocumentRecord) -> KnowledgeDocument:
        return KnowledgeDocument.model_validate({
            "id": record.id,
            "title": record.title,
            "original_filename": record.original_filename,
            "file_hash": record.file_hash,
            "business": record.business,
            "document_type": record.document_type,
            "region": record.region,
            "authority": record.authority,
            "version": record.version,
            "effective_from": record.effective_from,
            "effective_to": record.effective_to,
            "status": record.status,
            "file_path": record.file_path,
            "page_count": record.page_count,
            "chunk_count": record.chunk_count,
            "error_message": record.error_message,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        })
