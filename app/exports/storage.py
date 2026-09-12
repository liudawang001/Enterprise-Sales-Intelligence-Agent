from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.exports.hashing import content_sha256
from app.exports.models import StoredExport
from app.exports.sanitizer import sanitize_filename


class ExportStorage(Protocol):
    def save(self, export_id: str, file_name: str, content: bytes) -> StoredExport: ...

    def open(self, export_id: str) -> Path: ...
    def exists(self, export_id: str) -> bool: ...
    def delete(self, export_id: str) -> None: ...


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

    def exists(self, export_id: str) -> bool:
        path = self._paths.get(export_id)
        return bool(path and path.is_file())

    def delete(self, export_id: str) -> None:
        path = self._paths.pop(export_id, None)
        if path and path.is_file():
            path.unlink()


class S3CompatibleExportStorage:
    def __init__(self, *, bucket: str, endpoint_url: str = "", region: str = "", access_key_id: str = "", secret_access_key: str = "", signed_url_ttl_seconds: int = 300) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required for S3 export storage") from exc
        self.bucket = bucket
        self.signed_url_ttl_seconds = signed_url_ttl_seconds
        self.client = boto3.client("s3", endpoint_url=endpoint_url or None, region_name=region or None, aws_access_key_id=access_key_id or None, aws_secret_access_key=secret_access_key or None)
        self._keys: dict[str, str] = {}

    def save(self, export_id: str, file_name: str, content: bytes) -> StoredExport:
        safe_name = sanitize_filename(file_name)
        key = f"exports/{export_id}/{safe_name}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ServerSideEncryption="AES256")
        self._keys[export_id] = key
        return StoredExport(artifact_path=f"s3://{self.bucket}/{key}", file_name=safe_name, file_size=len(content), sha256=content_sha256(content))

    def open(self, export_id: str) -> Path:
        raise FileNotFoundError("S3_ARTIFACT_REQUIRES_SIGNED_URL")

    def exists(self, export_id: str) -> bool:
        key = self._keys.get(export_id)
        if not key:
            return False
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def delete(self, export_id: str) -> None:
        key = self._keys.pop(export_id, None)
        if key:
            self.client.delete_object(Bucket=self.bucket, Key=key)

    def signed_url(self, export_id: str) -> str:
        key = self._keys.get(export_id)
        if not key:
            raise FileNotFoundError("EXPORT_ARTIFACT_NOT_FOUND")
        return self.client.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=self.signed_url_ttl_seconds)
