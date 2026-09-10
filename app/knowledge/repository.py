from copy import deepcopy
from datetime import date
from uuid import UUID

from app.knowledge.enums import DocumentStatus
from app.knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeFilter


class InMemoryKnowledgeRepository:
    """Deterministic repository used by local demos and unit tests."""

    def __init__(self) -> None:
        self.documents: dict[UUID, KnowledgeDocument] = {}
        self.chunks: dict[UUID, KnowledgeChunk] = {}

    def create_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        existing = self.find_by_hash(document.file_hash)
        if existing and existing.status == DocumentStatus.READY:
            return deepcopy(existing)
        self.documents[document.id] = deepcopy(document)
        return deepcopy(document)

    def find_by_hash(self, file_hash: str) -> KnowledgeDocument | None:
        return next((deepcopy(doc) for doc in self.documents.values() if doc.file_hash == file_hash), None)

    def get_document(self, document_id: UUID) -> KnowledgeDocument | None:
        doc = self.documents.get(document_id)
        return deepcopy(doc) if doc else None

    def list_documents(self) -> list[KnowledgeDocument]:
        return [deepcopy(doc) for doc in self.documents.values()]

    def update_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        self.documents[document.id] = deepcopy(document)
        return deepcopy(document)

    def replace_chunks(self, document_id: UUID, chunks: list[KnowledgeChunk]) -> None:
        for chunk_id, chunk in list(self.chunks.items()):
            if chunk.document_id == document_id:
                del self.chunks[chunk_id]
        for chunk in chunks:
            self.chunks[chunk.id] = deepcopy(chunk)

    def list_chunks(self, document_id: UUID | None = None, knowledge_filter: KnowledgeFilter | None = None) -> list[KnowledgeChunk]:
        result: list[KnowledgeChunk] = []
        knowledge_filter = knowledge_filter or KnowledgeFilter()
        for chunk in self.chunks.values():
            doc = self.documents.get(chunk.document_id)
            if doc is None or not self._matches(doc, knowledge_filter):
                continue
            if document_id and chunk.document_id != document_id:
                continue
            result.append(deepcopy(chunk))
        return result

    @staticmethod
    def _matches(doc: KnowledgeDocument, knowledge_filter: KnowledgeFilter) -> bool:
        if knowledge_filter.statuses and doc.status not in knowledge_filter.statuses:
            return False
        if knowledge_filter.businesses and doc.business not in knowledge_filter.businesses:
            return False
        if knowledge_filter.document_types and doc.document_type not in knowledge_filter.document_types:
            return False
        if knowledge_filter.authorities and doc.authority not in knowledge_filter.authorities:
            return False
        if knowledge_filter.regions and doc.region not in knowledge_filter.regions:
            return False
        if knowledge_filter.effective_at:
            at = knowledge_filter.effective_at
            if doc.effective_from and doc.effective_from > at:
                return False
            if doc.effective_to and doc.effective_to < at:
                return False
        return True
