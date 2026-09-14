import asyncio
from datetime import date
from typing import Any

from app.knowledge.enums import DocumentAuthority, DocumentStatus
from app.knowledge.ingestion.chunker import StructureAwareChunker
from app.knowledge.ingestion.storage import LocalFileStorage
from app.knowledge.ingestion.validator import DocumentValidationError, sha256_bytes, validate_pdf
from app.knowledge.models import KnowledgeDocument
from app.knowledge.parsers.pdf import PdfDocumentParser
from app.knowledge.repository import InMemoryKnowledgeRepository
from app.providers.embedding.fake import DeterministicFakeEmbedding


class DocumentIngestionService:
    def __init__(self, repository: InMemoryKnowledgeRepository, *, storage: LocalFileStorage | None = None, parser: Any | None = None, chunker: StructureAwareChunker | None = None, embedding: Any | None = None) -> None:
        self.repository = repository
        self.storage = storage or LocalFileStorage()
        self.parser = parser or PdfDocumentParser()
        self.chunker = chunker or StructureAwareChunker()
        self.embedding = embedding or DeterministicFakeEmbedding()

    async def ingest(self, *, filename: str, content: bytes, title: str, business: str | None = None, document_type: str | None = None, region: str = "NATIONAL", authority: DocumentAuthority = DocumentAuthority.DEMO, version: str | None = None, effective_from: date | None = None, effective_to: date | None = None, access_scope: str = "GLOBAL", workspace_id: str | None = None) -> KnowledgeDocument:
        file_hash = sha256_bytes(content)
        existing = self.repository.find_by_hash(file_hash, workspace_id=workspace_id, access_scope=access_scope)
        if existing and existing.status == DocumentStatus.READY:
            return existing
        validate_pdf(filename, content)
        document = KnowledgeDocument(title=title, original_filename=filename, file_hash=file_hash, business=business, document_type=document_type, region=region, authority=authority, version=version, effective_from=effective_from, effective_to=effective_to, access_scope=access_scope, workspace_id=workspace_id if access_scope == "WORKSPACE" else None, status=DocumentStatus.UPLOADED, file_path="")
        self.repository.create_document(document)
        saved_path = ""
        try:
            saved_path = await self.storage.save(filename, content, file_hash=file_hash)
            document.file_path = saved_path
            document.status = DocumentStatus.PARSING
            self.repository.update_document(document)
            parsed = await self.parser.parse(saved_path)
            document.page_count = len(parsed.pages)
            document.status = DocumentStatus.INDEXING
            self.repository.update_document(document)
            chunks = self.chunker.chunk(parsed, document_metadata={"document_id": str(document.id), "document_title": document.title, "business": business, "document_type": document_type, "region": region, "authority": authority.value, "version": version, "effective_from": effective_from.isoformat() if effective_from else None, "effective_to": effective_to.isoformat() if effective_to else None, "access_scope": access_scope, "workspace_id": document.workspace_id})
            texts = [chunk.content for chunk in chunks]
            if hasattr(self.embedding, "aembed_documents"):
                vectors = await self.embedding.aembed_documents(texts)
            else:
                vectors = await asyncio.to_thread(self.embedding.embed_documents, texts)
            if len(vectors) != len(chunks):
                raise ValueError("EMBEDDING_RESULT_COUNT_MISMATCH")
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk.embedding = vector
                profile = getattr(self.embedding, "profile_version", None)
                if profile:
                    chunk.metadata["embedding_profile_version"] = profile
                    chunk.metadata["embedding_model"] = getattr(self.embedding, "model", None)
            self.repository.replace_chunks(document.id, chunks)
            document.chunk_count = len(chunks)
            profile = getattr(self.embedding, "profile_version", None)
            if profile:
                document.embedding_provider = getattr(self.embedding, "provider", "")
                document.embedding_model = getattr(self.embedding, "model", "")
                document.embedding_dimension = getattr(self.embedding, "dimension", None)
                document.embedding_profile_version = profile
            document.status = DocumentStatus.READY
            return self.repository.update_document(document)
        except Exception as exc:
            document.status = DocumentStatus.FAILED
            document.error_message = str(exc)
            self.repository.update_document(document)
            if saved_path:
                await self.storage.delete(saved_path)
            return document

    async def reindex(self, document_id) -> KnowledgeDocument:
        document = self.repository.get_document(document_id)
        if not document:
            raise KeyError(str(document_id))
        try:
            # Reindex in place so a READY document with the same file hash is not
            # short-circuited by the upload idempotency check.
            parsed = await self.parser.parse(document.file_path)
            chunks = self.chunker.chunk(parsed, document_metadata={"document_id": str(document.id), "document_title": document.title, "business": document.business, "document_type": document.document_type, "region": document.region, "authority": document.authority.value, "version": document.version, "effective_from": document.effective_from.isoformat() if document.effective_from else None, "effective_to": document.effective_to.isoformat() if document.effective_to else None, "access_scope": document.access_scope, "workspace_id": document.workspace_id})
            texts = [chunk.content for chunk in chunks]
            vectors = await self.embedding.aembed_documents(texts) if hasattr(self.embedding, "aembed_documents") else await asyncio.to_thread(self.embedding.embed_documents, texts)
            if len(vectors) != len(chunks):
                raise ValueError("EMBEDDING_RESULT_COUNT_MISMATCH")
            profile = getattr(self.embedding, "profile_version", None)
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk.embedding = vector
                if profile:
                    chunk.metadata["embedding_profile_version"] = profile
            document.page_count = len(parsed.pages)
            document.chunk_count = len(chunks)
            document.status = DocumentStatus.READY
            if profile:
                document.embedding_provider = getattr(self.embedding, "provider", "")
                document.embedding_model = getattr(self.embedding, "model", "")
                document.embedding_dimension = getattr(self.embedding, "dimension", None)
                document.embedding_profile_version = profile
            self.repository.replace_chunks(document.id, chunks)
            return self.repository.update_document(document)
        except Exception as exc:
            document.status = DocumentStatus.FAILED
            document.error_message = str(exc)
            return self.repository.update_document(document)

    def disable(self, document_id) -> KnowledgeDocument:
        document = self.repository.get_document(document_id)
        if not document:
            raise KeyError(str(document_id))
        document.status = DocumentStatus.DISABLED
        return self.repository.update_document(document)
