from typing import Any

from app.knowledge.retrieval.models import RetrievalHit


class BGEReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        self.model_name = model_name
        self._model: Any = None

    async def rerank(self, query: str, hits: list[RetrievalHit], top_k: int) -> list[RetrievalHit]:
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
        scores = self._model.predict([(query, hit.content) for hit in hits])
        for hit, score in zip(hits, scores, strict=True):
            hit.rerank_score = float(score)
        return sorted(hits, key=lambda hit: hit.rerank_score or 0, reverse=True)[:top_k]
