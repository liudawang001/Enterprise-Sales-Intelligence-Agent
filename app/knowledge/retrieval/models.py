from typing import Any

from pydantic import BaseModel


class RetrievalHit(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    dense_rank: int | None = None
    sparse_rank: int | None = None
    dense_score: float | None = None
    sparse_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None
    page_start: int
    page_end: int
    metadata: dict[str, Any]
