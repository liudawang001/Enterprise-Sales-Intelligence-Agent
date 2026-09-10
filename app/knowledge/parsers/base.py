from typing import Protocol

from app.knowledge.models import ParsedDocument


class DocumentParser(Protocol):
    async def parse(self, file_path: str) -> ParsedDocument:
        ...
