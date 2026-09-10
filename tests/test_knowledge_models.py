from datetime import date

from app.knowledge.enums import ChunkType, DocumentAuthority, DocumentStatus
from app.knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeFilter, KnowledgeQuery
from app.knowledge.repository import InMemoryKnowledgeRepository


def test_document_chunk_models_and_repository_filters() -> None:
    repository = InMemoryKnowledgeRepository()
    document = KnowledgeDocument(
        title="集团V网 Demo 业务说明",
        original_filename="demo.pdf",
        file_hash="a" * 64,
        business="集团V网",
        region="SHANGHAI",
        authority=DocumentAuthority.DEMO,
        effective_from=date(2026, 1, 1),
        status=DocumentStatus.READY,
        file_path="data/demo.pdf",
    )
    repository.create_document(document)
    chunk = KnowledgeChunk(
        document_id=document.id,
        chunk_index=0,
        content="集团V网适合集团客户。",
        lexical_content="集团 V 网 适合 集团 客户",
        chunk_type=ChunkType.PARAGRAPH,
        page_start=2,
        page_end=2,
        content_hash="b" * 64,
    )
    repository.replace_chunks(document.id, [chunk])

    assert len(repository.list_chunks(knowledge_filter=KnowledgeFilter(businesses=["集团V网"]))) == 1
    assert repository.list_chunks(knowledge_filter=KnowledgeFilter(effective_at=date(2025, 1, 1))) == []
    assert KnowledgeQuery(raw_query="问题", rewritten_query="问题").current_only is True
