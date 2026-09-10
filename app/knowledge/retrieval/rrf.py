from collections import defaultdict

from app.knowledge.retrieval.models import RetrievalHit


class ReciprocalRankFusion:
    def __init__(self, k: int = 60) -> None:
        self.k = k

    def fuse(self, dense_hits: list[RetrievalHit], sparse_hits: list[RetrievalHit], *, top_k: int) -> list[RetrievalHit]:
        merged: dict[str, RetrievalHit] = {}
        scores = defaultdict(float)
        for rank, hit in enumerate(dense_hits, start=1):
            merged.setdefault(hit.chunk_id, hit).dense_rank = hit.dense_rank or rank
            scores[hit.chunk_id] += 1 / (self.k + rank)
        for rank, hit in enumerate(sparse_hits, start=1):
            if hit.chunk_id not in merged:
                merged[hit.chunk_id] = hit
            else:
                merged[hit.chunk_id].sparse_rank = hit.sparse_rank or rank
                merged[hit.chunk_id].sparse_score = hit.sparse_score
            scores[hit.chunk_id] += 1 / (self.k + rank)
        for chunk_id, hit in merged.items():
            hit.fusion_score = scores[chunk_id]
        return sorted(merged.values(), key=lambda hit: hit.fusion_score or 0, reverse=True)[:top_k]
