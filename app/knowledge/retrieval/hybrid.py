from app.knowledge.models import KnowledgeFilter
from app.knowledge.retrieval.dense import DenseRetriever
from app.knowledge.retrieval.models import RetrievalHit
from app.knowledge.retrieval.rrf import ReciprocalRankFusion
from app.knowledge.retrieval.sparse import PostgresSparseRetriever
from app.knowledge.rerank.base import Reranker


class HybridRetriever:
    def __init__(self, dense: DenseRetriever, sparse: PostgresSparseRetriever, fusion: ReciprocalRankFusion, reranker: Reranker | None = None) -> None:
        self.dense = dense
        self.sparse = sparse
        self.fusion = fusion
        self.reranker = reranker

    async def search(self, query: str, *, knowledge_filter: KnowledgeFilter, dense_top_k: int = 20, sparse_top_k: int = 20, fusion_top_k: int = 12, rerank_top_k: int = 6) -> tuple[list[RetrievalHit], list[str]]:
        warnings: list[str] = []
        try:
            dense_hits = self.dense.search(query, knowledge_filter=knowledge_filter, top_k=dense_top_k)
        except Exception:
            dense_hits = []
            warnings.append("DENSE_RETRIEVAL_DEGRADED")
        try:
            sparse_hits = self.sparse.search(query, knowledge_filter=knowledge_filter, top_k=sparse_top_k)
        except Exception:
            sparse_hits = []
            warnings.append("SPARSE_RETRIEVAL_DEGRADED")
        if not dense_hits and not sparse_hits:
            return [], warnings + ["RAG_FAILED"]
        fused = self.fusion.fuse(dense_hits, sparse_hits, top_k=fusion_top_k)
        if self.reranker is None:
            return fused[:rerank_top_k], warnings
        try:
            return await self.reranker.rerank(query, fused, rerank_top_k), warnings
        except Exception:
            warnings.append("RERANKER_DEGRADED")
            return fused[:rerank_top_k], warnings
