from typing import Protocol

from app.knowledge.retrieval.models import RetrievalHit


class Reranker(Protocol):
    async def rerank(self, query: str, hits: list[RetrievalHit], top_k: int) -> list[RetrievalHit]:
        ...
