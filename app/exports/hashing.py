import hashlib
import json


def export_request_hash(payload: dict) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
