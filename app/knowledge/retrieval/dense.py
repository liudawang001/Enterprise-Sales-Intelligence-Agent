import math
import asyncio

from app.knowledge.models import KnowledgeFilter
from app.knowledge.repository import InMemoryKnowledgeRepository
from app.knowledge.retrieval.models import RetrievalHit
from app.providers.embedding.base import EmbeddingProvider


class DenseRetriever:
    def __init__(self, repository: InMemoryKnowledgeRepository, embedding: EmbeddingProvider) -> None:
        self.repository = repository
        self.embedding = embedding

    def search(self, query: str, *, knowledge_filter: KnowledgeFilter, top_k: int) -> list[RetrievalHit]:
        sql_search = getattr(self.repository, "dense_search", None)
        if sql_search is not None:
            return sql_search(query, embedding=self.embedding, knowledge_filter=knowledge_filter, top_k=top_k)
        query_vector = self.embedding.embed_query(query)
        scored: list[tuple[float, object]] = []
        for chunk in self.repository.list_chunks(knowledge_filter=knowledge_filter):
            if not chunk.embedding:
                continue
            score = self._cosine(query_vector, chunk.embedding)
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [RetrievalHit(chunk_id=str(chunk.id), document_id=str(chunk.document_id), content=chunk.content, dense_rank=index, dense_score=score, page_start=chunk.page_start, page_end=chunk.page_end, metadata=chunk.metadata) for index, (score, chunk) in enumerate(scored[:top_k], start=1)]

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = math.sqrt(sum(value * value for value in left)) or 1.0
        right_norm = math.sqrt(sum(value * value for value in right)) or 1.0
        return numerator / (left_norm * right_norm)

    async def asearch(self, query: str, *, knowledge_filter: KnowledgeFilter, top_k: int) -> list[RetrievalHit]:
        provider_method = getattr(self.embedding, "aembed_query", None)
        if provider_method is None:
            return await asyncio.to_thread(self.search, query, knowledge_filter=knowledge_filter, top_k=top_k)
        query_vector = await provider_method(query)
        sql_search = getattr(self.repository, "dense_search_vector", None)
        if sql_search is not None:
            return sql_search(query_vector, knowledge_filter=knowledge_filter, top_k=top_k)
        scored: list[tuple[float, object]] = []
        for chunk in self.repository.list_chunks(knowledge_filter=knowledge_filter):
            if chunk.embedding:
                scored.append((self._cosine(query_vector, chunk.embedding), chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [RetrievalHit(chunk_id=str(chunk.id), document_id=str(chunk.document_id), content=chunk.content, dense_rank=index, dense_score=score, page_start=chunk.page_start, page_end=chunk.page_end, metadata=chunk.metadata) for index, (score, chunk) in enumerate(scored[:top_k], start=1)]
