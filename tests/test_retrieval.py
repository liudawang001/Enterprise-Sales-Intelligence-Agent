from datetime import date
from uuid import uuid4

import pytest

from app.knowledge.enums import DocumentAuthority, DocumentStatus
from app.knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeFilter, KnowledgeQuery
from app.knowledge.repository import InMemoryKnowledgeRepository
from app.knowledge.retrieval.dense import DenseRetriever
from app.knowledge.retrieval.filters import MetadataFilterBuilder
from app.knowledge.retrieval.rrf import ReciprocalRankFusion
from app.knowledge.retrieval.sparse import PostgresSparseRetriever
from app.knowledge.rerank.fake import FakeReranker
from app.providers.embedding.fake import DeterministicFakeEmbedding
from app.knowledge.ingestion.tokenizer import JiebaLexicalTokenizer


def _repository() -> InMemoryKnowledgeRepository:
    repository = InMemoryKnowledgeRepository()
    doc = KnowledgeDocument(id=uuid4(), title="Demo", original_filename="demo.pdf", file_hash="c" * 64, business="集团V网", region="NATIONAL", authority=DocumentAuthority.DEMO, status=DocumentStatus.READY, file_path="demo.pdf", effective_from=date(2026, 1, 1))
    repository.create_document(doc)
    embedding = DeterministicFakeEmbedding(32)
    chunks = []
    for index, content in enumerate(["集团V网适合企业客户", "短号和跨省V网属于通信业务"], start=1):
        chunks.append(KnowledgeChunk(id=uuid4(), document_id=doc.id, chunk_index=index, content=content, lexical_content=JiebaLexicalTokenizer().tokenize(content), embedding=embedding.embed_query(content), page_start=index, page_end=index, content_hash=str(index) * 64))
    repository.replace_chunks(doc.id, chunks)
    return repository


@pytest.mark.asyncio
async def test_dense_sparse_rrf_and_rerank():
    repository = _repository()
    filter_ = MetadataFilterBuilder().build(KnowledgeQuery(raw_query="集团V网", rewritten_query="集团V网", business="集团V网"))
    dense = DenseRetriever(repository, DeterministicFakeEmbedding(32)).search("集团V网", knowledge_filter=filter_, top_k=2)
    sparse = PostgresSparseRetriever(repository, JiebaLexicalTokenizer()).search("短号", knowledge_filter=filter_, top_k=2)
    fused = ReciprocalRankFusion().fuse(dense, sparse, top_k=2)
    reranked = await FakeReranker().rerank("集团V网", fused, top_k=1)
    assert dense and sparse and fused
    assert len(reranked) == 1
    assert reranked[0].rerank_score is not None


def test_metadata_filter_excludes_expired_document():
    repository = _repository()
    document = repository.list_documents()[0]
    document.effective_to = date(2025, 12, 31)
    repository.update_document(document)
    filter_ = MetadataFilterBuilder().build(KnowledgeQuery(raw_query="集团V网", rewritten_query="集团V网", business="集团V网"))
    assert repository.list_chunks(knowledge_filter=filter_) == []
