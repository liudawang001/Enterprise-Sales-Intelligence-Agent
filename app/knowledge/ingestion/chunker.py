import hashlib
import re
from dataclasses import dataclass

from app.knowledge.enums import ChunkType
from app.knowledge.models import KnowledgeChunk, ParsedDocument, ParsedPage
from app.knowledge.ingestion.tokenizer import JiebaLexicalTokenizer, LexicalTokenizer


@dataclass(frozen=True)
class ChunkerConfig:
    chunk_size: int = 900
    chunk_overlap: int = 120


def content_hash(content: str, page: int, section_path: str | None) -> str:
    normalized = re.sub(r"\s+", " ", content).strip()
    raw = f"{normalized}|{page}|{section_path or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class StructureAwareChunker:
    def __init__(self, config: ChunkerConfig | None = None, tokenizer: LexicalTokenizer | None = None) -> None:
        self.config = config or ChunkerConfig()
        self.tokenizer = tokenizer or JiebaLexicalTokenizer()

    def chunk(self, parsed: ParsedDocument, *, document_metadata: dict) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        for page in parsed.pages:
            blocks = page.blocks or [{"type": "text", "text": page.text}]
            section_path: str | None = None
            for block in blocks:
                text = str(block.get("text", "")).strip()
                if not text:
                    continue
                kind = str(block.get("type", "text")).lower()
                if self._is_heading(text):
                    section_path = text[:160]
                chunk_type = ChunkType.TABLE if kind == "table" else (ChunkType.SECTION if self._is_heading(text) else ChunkType.PARAGRAPH)
                pieces = self._split_long(text) if len(text) > self.config.chunk_size else [text]
                for piece in pieces:
                    chunks.append(self._make_chunk(piece, page, section_path, chunk_type, document_metadata, len(chunks)))
        return chunks

    def _make_chunk(self, text: str, page: ParsedPage, section_path: str | None, chunk_type: ChunkType, metadata: dict, index: int) -> KnowledgeChunk:
        chunk_metadata = {
            **metadata,
            "page_start": page.page_number,
            "page_end": page.page_number,
            "section_path": section_path,
            "chunk_type": chunk_type.value,
            "chunk_index": index,
        }
        return KnowledgeChunk(
            document_id=metadata["document_id"],
            chunk_index=index,
            content=text,
            lexical_content=self.tokenizer.tokenize(text),
            chunk_type=chunk_type,
            page_start=page.page_number,
            page_end=page.page_number,
            section_path=section_path,
            content_hash=content_hash(text, page.page_number, section_path),
            metadata=chunk_metadata,
        )

    def _split_long(self, text: str) -> list[str]:
        paragraphs = [part.strip() for part in re.split(r"\n{2,}|(?<=[。！？.!?])", text) if part.strip()]
        if not paragraphs:
            paragraphs = [text]
        pieces: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if len(current) + len(paragraph) + 1 <= self.config.chunk_size:
                current = f"{current}\n{paragraph}".strip()
            else:
                if current:
                    pieces.append(current)
                if len(paragraph) <= self.config.chunk_size:
                    current = paragraph
                else:
                    step = max(1, self.config.chunk_size - self.config.chunk_overlap)
                    pieces.extend(paragraph[start : start + self.config.chunk_size] for start in range(0, len(paragraph), step))
                    current = ""
        if current:
            pieces.append(current)
        return pieces

    @staticmethod
    def _is_heading(text: str) -> bool:
        return len(text) <= 80 and (bool(re.match(r"^(第[一二三四五六七八九十\d]+[章节部分]|[一二三四五六七八九十\d]+[、.])", text)) or text.isupper())
