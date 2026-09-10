from app.knowledge.retrieval.models import RetrievalHit


class FakeReranker:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def rerank(self, query: str, hits: list[RetrievalHit], top_k: int) -> list[RetrievalHit]:
        if self.fail:
            raise RuntimeError("fake reranker failure")
        query_terms = set(query.split())
        ranked = sorted(hits, key=lambda hit: (len(query_terms & set(hit.content.split())), hit.fusion_score or 0), reverse=True)
        for index, hit in enumerate(ranked[:top_k], start=1):
            hit.rerank_score = float(top_k - index + 1) / top_k
        return ranked[:top_k]
