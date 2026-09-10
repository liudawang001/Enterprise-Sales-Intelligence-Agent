from app.knowledge.ingestion.tokenizer import LexicalTokenizer
from app.knowledge.models import KnowledgeFilter
from app.knowledge.repository import InMemoryKnowledgeRepository
from app.knowledge.retrieval.models import RetrievalHit


class PostgresSparseRetriever:
    """In-memory lexical implementation mirroring the PostgreSQL simple-tsvector contract."""

    def __init__(self, repository: InMemoryKnowledgeRepository, tokenizer: LexicalTokenizer) -> None:
        self.repository = repository
        self.tokenizer = tokenizer

    def search(self, query: str, *, knowledge_filter: KnowledgeFilter, top_k: int) -> list[RetrievalHit]:
        terms = set(self.tokenizer.tokenize(query).split())
        scored: list[tuple[float, object]] = []
        for chunk in self.repository.list_chunks(knowledge_filter=knowledge_filter):
            tokens = set(chunk.lexical_content.split())
            overlap = len(terms & tokens)
            if overlap:
                scored.append((overlap / max(len(terms), 1), chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [RetrievalHit(chunk_id=str(chunk.id), document_id=str(chunk.document_id), content=chunk.content, sparse_rank=index, sparse_score=score, page_start=chunk.page_start, page_end=chunk.page_end, metadata=chunk.metadata) for index, (score, chunk) in enumerate(scored[:top_k], start=1)]
