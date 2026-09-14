from uuid import uuid4

from app.knowledge.enums import DocumentStatus
from app.knowledge.models import KnowledgeDocument, KnowledgeFilter
from app.knowledge.repository import InMemoryKnowledgeRepository


def test_profile_filter_excludes_stale_or_fake_documents():
    repository = InMemoryKnowledgeRepository()
    repository.create_document(KnowledgeDocument(title="old", original_filename="old.pdf", file_hash="a" * 64, status=DocumentStatus.READY, file_path="old.pdf"))
    repository.create_document(KnowledgeDocument(id=uuid4(), title="current", original_filename="current.pdf", file_hash="b" * 64, status=DocumentStatus.READY, file_path="current.pdf", embedding_profile_version="qwen3.7-text-embedding:1024:v1"))
    matched = [doc for doc in repository.list_documents() if repository._matches(doc, KnowledgeFilter(embedding_profile_version="qwen3.7-text-embedding:1024:v1"))]
    assert [doc.title for doc in matched] == ["current"]
