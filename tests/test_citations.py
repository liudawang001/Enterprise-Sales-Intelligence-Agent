import pytest

from app.knowledge.citation.builder import build_citations
from app.knowledge.citation.validator import CitationValidationError, CitationValidator
from app.knowledge.retrieval.models import RetrievalHit


def test_citation_builder_and_validator():
    hit = RetrievalHit(chunk_id="c1", document_id="d1", content="集团V网适合集团客户", page_start=2, page_end=2, metadata={"document_title": "Demo"})
    citations = build_citations([hit])
    assert citations[0]["page_start"] == 2
    assert CitationValidator().validate("结论[1]", citations) == "结论[1]"
    with pytest.raises(CitationValidationError):
        CitationValidator().validate("结论[9]", citations)
