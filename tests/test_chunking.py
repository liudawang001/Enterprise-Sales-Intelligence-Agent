from uuid import uuid4

from app.knowledge.enums import ChunkType
from app.knowledge.ingestion.chunker import ChunkerConfig, StructureAwareChunker, content_hash
from app.knowledge.models import ParsedDocument, ParsedPage


def test_structure_aware_chunking_preserves_pages_and_metadata() -> None:
    document_id = str(uuid4())
    parsed = ParsedDocument(
        document_id=document_id,
        pages=[ParsedPage(page_number=2, text="第1章 业务说明\n集团V网适合集团客户。", blocks=[
            {"type": "text", "text": "第1章 业务说明"},
            {"type": "text", "text": "集团V网适合集团客户。"},
        ])],
    )
    chunks = StructureAwareChunker().chunk(parsed, document_metadata={"document_id": document_id, "business": "集团V网"})
    assert len(chunks) == 2
    assert chunks[0].chunk_type == ChunkType.SECTION
    assert all(chunk.page_start == 2 for chunk in chunks)
    assert "集团" in chunks[1].lexical_content
    assert chunks[0].metadata["business"] == "集团V网"


def test_long_block_is_split_and_hash_is_deterministic() -> None:
    document_id = str(uuid4())
    text = "集团V网适合企业客户。" * 100
    parsed = ParsedDocument(document_id=document_id, pages=[ParsedPage(page_number=1, text=text)])
    chunks = StructureAwareChunker(ChunkerConfig(chunk_size=100, chunk_overlap=10)).chunk(parsed, document_metadata={"document_id": document_id})
    assert len(chunks) > 1
    assert content_hash("abc", 1, "s") == content_hash(" abc ", 1, "s")
