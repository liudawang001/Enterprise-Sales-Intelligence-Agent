import pytest

from app.knowledge.ingestion.tokenizer import JiebaLexicalTokenizer
from app.knowledge.models import KnowledgeQuery
from app.knowledge.rerank.fake import FakeReranker
from app.knowledge.retrieval.dense import DenseRetriever
from app.knowledge.retrieval.filters import MetadataFilterBuilder
from app.knowledge.retrieval.hybrid import HybridRetriever
from app.knowledge.retrieval.rrf import ReciprocalRankFusion
from app.knowledge.retrieval.sparse import PostgresSparseRetriever
from app.providers.embedding.fake import DeterministicFakeEmbedding
from tests.test_retrieval import _repository


@pytest.mark.asyncio
async def test_reranker_failure_falls_back_to_rrf():
    repository = _repository()
    filter_ = MetadataFilterBuilder().build(KnowledgeQuery(raw_query="集团V网", rewritten_query="集团V网", business="集团V网"))
    hybrid = HybridRetriever(DenseRetriever(repository, DeterministicFakeEmbedding(32)), PostgresSparseRetriever(repository, JiebaLexicalTokenizer()), ReciprocalRankFusion(), FakeReranker(fail=True))
    hits, warnings = await hybrid.search("集团V网", knowledge_filter=filter_, fusion_top_k=2, rerank_top_k=1)
    assert len(hits) == 1
    assert "RERANKER_DEGRADED" in warnings
