from __future__ import annotations

import re
from pathlib import PurePath
from urllib.parse import urlparse

FORMULA_PREFIXES = ("=", "+", "-", "@")


def normalize_text(value: object) -> str:
    text = str(value).replace("\x00", "")
    return "".join(char for char in text if char in "\n\r\t" or ord(char) >= 32).strip()


def safe_spreadsheet_text(value: object) -> str:
    text = normalize_text(value)
    if text.lstrip().startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def safe_http_url(value: object | None) -> str | None:
    if value is None:
        return None
    text = normalize_text(value)
    parsed = urlparse(text)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return text


def sanitize_filename(value: str | None, *, default: str = "lead_export.xlsx") -> str:
    raw = normalize_text(value or default)
    raw = raw.replace("/", "_").replace("\\", "_")
    raw = re.sub(r"[<>:\"|?*]", "_", raw)
    raw = re.sub(r"\.{2,}", "_", raw)
    raw = PurePath(raw).name.strip(" .")
    if not raw:
        raw = default
    stem = raw[:-5] if raw.lower().endswith(".xlsx") else raw
    stem = stem[:100].rstrip(" ._") or "lead_export"
    return f"{stem}.xlsx"
