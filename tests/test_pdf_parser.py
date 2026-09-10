from pathlib import Path

import fitz
import pytest

from app.knowledge.ingestion.storage import LocalFileStorage
from app.knowledge.ingestion.validator import DocumentValidationError, sha256_bytes, validate_pdf
from app.knowledge.parsers.pdf import PdfDocumentParser, UnsupportedScannedPdfError


def _pdf(path: Path, texts: list[str]) -> bytes:
    doc = fitz.open()
    for text in texts:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    data = doc.tobytes()
    path.write_bytes(data)
    return data


@pytest.mark.asyncio
async def test_pdf_parser_preserves_page_numbers_and_storage(tmp_path: Path) -> None:
    source = tmp_path / "demo.pdf"
    data = _pdf(source, ["Page one Group VNet", "Page two eligibility"])
    validate_pdf(source.name, data)
    parsed = await PdfDocumentParser().parse(str(source))
    assert [page.page_number for page in parsed.pages] == [1, 2]
    assert "Group VNet" in parsed.pages[0].text
    storage = LocalFileStorage(str(tmp_path / "uploads"))
    saved = await storage.save(source.name, data, file_hash=sha256_bytes(data))
    assert Path(saved).exists()


def test_invalid_pdf_is_rejected() -> None:
    with pytest.raises(DocumentValidationError) as exc:
        validate_pdf("notes.txt", b"not pdf")
    assert exc.value.code == "INVALID_DOCUMENT"


@pytest.mark.asyncio
async def test_scanned_pdf_has_explicit_boundary(tmp_path: Path) -> None:
    source = tmp_path / "scanned.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), " ")
    source.write_bytes(doc.tobytes())
    with pytest.raises(UnsupportedScannedPdfError):
        await PdfDocumentParser().parse(str(source))
