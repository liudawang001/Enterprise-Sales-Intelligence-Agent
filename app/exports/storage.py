from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.exports.hashing import content_sha256
from app.exports.models import StoredExport
from app.exports.sanitizer import sanitize_filename


class ExportStorage(Protocol):
    def save(self, export_id: str, file_name: str, content: bytes) -> StoredExport: ...

    def open(self, export_id: str) -> Path: ...


class LocalExportStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._paths: dict[str, Path] = {}

    def save(self, export_id: str, file_name: str, content: bytes) -> StoredExport:
        safe_name = sanitize_filename(file_name)
        export_dir = (self.root / export_id).resolve()
        if export_dir.parent != self.root:
            raise ValueError("EXPORT_PATH_TRAVERSAL")
        export_dir.mkdir(parents=True, exist_ok=True)
        path = (export_dir / safe_name).resolve()
        if path.parent != export_dir:
            raise ValueError("EXPORT_PATH_TRAVERSAL")
        path.write_bytes(content)
        self._paths[export_id] = path
        return StoredExport(
            artifact_path=str(path),
            file_name=safe_name,
            file_size=len(content),
            sha256=content_sha256(content),
        )

    def open(self, export_id: str) -> Path:
        path = self._paths.get(export_id)
        if not path or not path.is_file():
            raise FileNotFoundError("EXPORT_ARTIFACT_NOT_FOUND")
        return path
