from app.knowledge.retrieval.models import RetrievalHit


def build_citations(hits: list[RetrievalHit]) -> list[dict]:
    return [
        {
            "citation_id": index,
            "document_id": hit.document_id,
            "chunk_id": hit.chunk_id,
            "document_title": hit.metadata.get("document_title", "Knowledge Document"),
            "page_start": hit.page_start,
            "page_end": hit.page_end,
            "section_path": hit.metadata.get("section_path"),
            "source_type": hit.metadata.get("authority", "DEMO"),
            "excerpt": hit.content[:240],
        }
        for index, hit in enumerate(hits, start=1)
    ]
