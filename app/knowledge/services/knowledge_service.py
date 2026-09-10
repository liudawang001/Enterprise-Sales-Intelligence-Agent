from datetime import date
import re
from uuid import UUID

from app.knowledge.citation.builder import build_citations
from app.knowledge.citation.validator import CitationValidator
from app.knowledge.models import KnowledgeQuery
from app.knowledge.repository import InMemoryKnowledgeRepository
from app.knowledge.retrieval.filters import MetadataFilterBuilder
from app.knowledge.retrieval.hybrid import HybridRetriever
from app.knowledge.retrieval.models import RetrievalHit
from app.knowledge.retrieval.rrf import ReciprocalRankFusion
from app.knowledge.retrieval.dense import DenseRetriever
from app.knowledge.retrieval.sparse import PostgresSparseRetriever
from app.knowledge.rerank.fake import FakeReranker
from app.knowledge.ingestion.tokenizer import JiebaLexicalTokenizer
from app.providers.embedding.fake import DeterministicFakeEmbedding
from app.providers.llm.fake import FakeChatModel


class KnowledgeService:
    def __init__(self, repository: InMemoryKnowledgeRepository, *, embedding=None, reranker=None, chat_model=None) -> None:
        self.repository = repository
        self.embedding = embedding or DeterministicFakeEmbedding()
        self.reranker = reranker or FakeReranker()
        self.chat_model = chat_model or FakeChatModel()
        self.filter_builder = MetadataFilterBuilder()
        self.hybrid = HybridRetriever(
            DenseRetriever(repository, self.embedding),
            PostgresSparseRetriever(repository, JiebaLexicalTokenizer()),
            ReciprocalRankFusion(),
            self.reranker,
        )

    def analyze_query(self, raw_query: str, *, context: list[str] | None = None) -> KnowledgeQuery:
        business = "集团V网" if "集团V网" in raw_query else ("企业专线" if "企业专线" in raw_query else None)
        region = "上海松江" if "松江" in raw_query else ("上海" if "上海" in raw_query else None)
        year_match = re.search(r"(20\d{2})年", raw_query)
        as_of_date = date(int(year_match.group(1)), 12, 31) if year_match else None
        rewritten = raw_query
        if business and ("适合" in raw_query or "客户" in raw_query):
            rewritten = f"{business}适用对象和办理条件"
        return KnowledgeQuery(raw_query=raw_query, rewritten_query=rewritten, business=business, region=region, as_of_date=as_of_date, current_only=as_of_date is None)

    def retrieve(self, query: KnowledgeQuery, *, top_k: int = 6) -> tuple[list[RetrievalHit], list[str]]:
        filter_ = self.filter_builder.build(query)
        # Keep the sync Graph path deterministic; the same HybridRetriever supports async callers.
        dense = self.hybrid.dense.search(query.rewritten_query, knowledge_filter=filter_, top_k=20)
        sparse = self.hybrid.sparse.search(query.rewritten_query, knowledge_filter=filter_, top_k=20)
        fused = self.hybrid.fusion.fuse(dense, sparse, top_k=12)
        if not fused:
            return [], ["NO_EVIDENCE"]
        return fused[:top_k], []

    def answer(self, question: str, query: KnowledgeQuery) -> dict:
        hits, warnings = self.retrieve(query)
        if not hits:
            return {"answer": "当前知识库中没有找到足够证据确认该问题。", "citations": [], "evidence_count": 0, "warnings": warnings + ["NO_EVIDENCE"]}
        citations = build_citations(hits)
        answer = self.chat_model.answer(question, hits)
        answer = CitationValidator().validate(answer, citations)
        return {"answer": answer, "citations": citations, "evidence_count": len(hits), "warnings": warnings}

    async def retrieve_async(self, query: KnowledgeQuery, *, top_k: int = 6) -> tuple[list[RetrievalHit], list[str]]:
        filter_ = self.filter_builder.build(query)
        hits, warnings = await self.hybrid.search(query.rewritten_query, knowledge_filter=filter_, fusion_top_k=12, rerank_top_k=top_k)
        return hits, warnings
