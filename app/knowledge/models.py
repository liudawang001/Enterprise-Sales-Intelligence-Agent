from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.knowledge.enums import ChunkType, DocumentAuthority, DocumentStatus


class KnowledgeDocument(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    original_filename: str
    file_hash: str
    business: str | None = None
    document_type: str | None = None
    region: str = "NATIONAL"
    authority: DocumentAuthority = DocumentAuthority.DEMO
    version: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    status: DocumentStatus = DocumentStatus.UPLOADED
    file_path: str
    page_count: int = 0
    chunk_count: int = 0
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeChunk(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    chunk_index: int
    content: str
    lexical_content: str
    embedding: list[float] | None = None
    chunk_type: ChunkType = ChunkType.PARAGRAPH
    page_start: int
    page_end: int
    section_path: str | None = None
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeFilter(BaseModel):
    businesses: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    document_types: list[str] = Field(default_factory=list)
    authorities: list[DocumentAuthority] = Field(default_factory=list)
    statuses: list[DocumentStatus] = Field(default_factory=lambda: [DocumentStatus.READY])
    effective_at: date | None = None


class KnowledgeQuery(BaseModel):
    raw_query: str
    rewritten_query: str
    business: str | None = None
    region: str | None = None
    as_of_date: date | None = None
    document_types: list[str] = Field(default_factory=list)
    current_only: bool = True


class ParsedPage(BaseModel):
    page_number: int
    text: str
    blocks: list[dict] = Field(default_factory=list)


class ParsedDocument(BaseModel):
    document_id: str
    pages: list[ParsedPage]
    metadata: dict = Field(default_factory=dict)
