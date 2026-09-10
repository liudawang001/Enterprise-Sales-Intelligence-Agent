from pathlib import Path
from uuid import uuid4

import fitz

from app.knowledge.models import ParsedDocument, ParsedPage


class UnsupportedScannedPdfError(ValueError):
    code = "UNSUPPORTED_SCANNED_PDF"


class PdfDocumentParser:
    async def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        try:
            document = fitz.open(path)
        except Exception as exc:
            raise ValueError(f"PDF_PARSE_FAILED: {exc}") from exc
        pages: list[ParsedPage] = []
        for index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            blocks = []
            for block in page.get_text("blocks"):
                if len(block) >= 5 and str(block[4]).strip():
                    blocks.append({"type": "text", "text": str(block[4]).strip()})
            if text:
                pages.append(ParsedPage(page_number=index, text=text, blocks=blocks))
        if not pages:
            raise UnsupportedScannedPdfError("No extractable text found")
        return ParsedDocument(document_id=str(uuid4()), pages=pages, metadata={"page_count": len(document)})
