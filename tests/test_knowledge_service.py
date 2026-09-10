from datetime import date
from uuid import uuid4

from app.knowledge.enums import DocumentAuthority, DocumentStatus
from app.knowledge.models import KnowledgeChunk, KnowledgeDocument
from app.knowledge.repository import InMemoryKnowledgeRepository
from app.knowledge.services.knowledge_service import KnowledgeService


def test_grounded_answer_has_traceable_citation() -> None:
    repository = InMemoryKnowledgeRepository()
    document = KnowledgeDocument(id=uuid4(), title="集团V网 Demo 业务说明", original_filename="demo.pdf", file_hash="d" * 64, business="集团V网", region="NATIONAL", authority=DocumentAuthority.DEMO, status=DocumentStatus.READY, file_path="demo.pdf", effective_from=date(2026, 1, 1))
    repository.create_document(document)
    service = KnowledgeService(repository)
    vector = service.embedding.embed_query("集团V网适合集团客户")
    repository.replace_chunks(document.id, [KnowledgeChunk(id=uuid4(), document_id=document.id, chunk_index=0, content="集团V网适合集团客户。", lexical_content="集团 V 网 适合 集团 客户", embedding=vector, page_start=2, page_end=2, content_hash="e" * 64, metadata={"document_title": document.title, "authority": "DEMO"})])

    result = service.answer("集团V网主要适合什么客户？", service.analyze_query("集团V网主要适合什么客户？"))
    assert result["evidence_count"] == 1
    assert "[1]" in result["answer"]
    assert result["citations"][0]["document_title"] == document.title
    assert result["citations"][0]["page_start"] == 2


def test_no_evidence_abstains_without_citation() -> None:
    service = KnowledgeService(InMemoryKnowledgeRepository())
    result = service.answer("虚构套餐X多少钱？", service.analyze_query("虚构套餐X多少钱？"))
    assert result["evidence_count"] == 0
    assert result["citations"] == []
    assert "没有找到足够证据" in result["answer"]
