"""SQLAlchemy knowledge models."""

from app.persistence.models.chunk import KnowledgeChunkRecord
from app.persistence.models.document import KnowledgeDocumentRecord

__all__ = ["KnowledgeChunkRecord", "KnowledgeDocumentRecord"]
