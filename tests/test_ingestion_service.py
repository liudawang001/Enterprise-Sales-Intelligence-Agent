from pathlib import Path

import fitz
import pytest

from app.knowledge.enums import DocumentStatus
from app.knowledge.ingestion.service import DocumentIngestionService
from app.knowledge.repository import InMemoryKnowledgeRepository


def _pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Group VNet serves enterprise customers.")
    return doc.tobytes()


@pytest.mark.asyncio
async def test_ingestion_is_ready_and_file_idempotent(tmp_path: Path) -> None:
    repository = InMemoryKnowledgeRepository()
    service = DocumentIngestionService(repository)
    service.storage.root = tmp_path
    content = _pdf()
    first = await service.ingest(filename="demo.pdf", content=content, title="Demo")
    second = await service.ingest(filename="demo.pdf", content=content, title="Demo")
    assert first.status == DocumentStatus.READY
    assert first.chunk_count > 0
    assert second.id == first.id
    assert len(repository.list_documents()) == 1


@pytest.mark.asyncio
async def test_ingestion_failure_is_marked_failed(tmp_path: Path) -> None:
    repository = InMemoryKnowledgeRepository()
    service = DocumentIngestionService(repository)
    service.storage.root = tmp_path
    result = await service.ingest(filename="broken.pdf", content=b"%PDF broken", title="Broken")
    assert result.status == DocumentStatus.FAILED
    assert result.error_message
