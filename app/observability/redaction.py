from __future__ import annotations

import re
from typing import Any

MASK = "[REDACTED]"
SECRET_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "api_key",
    "apikey",
    "password",
    "token",
    "jwt",
    "secret",
    "client_secret",
    "access_token",
    "refresh_token",
}
_KEY_VALUE = re.compile(r"(?i)(authorization|cookie|api[_-]?key|password|token|secret)\s*[:=]\s*([^\s,;]+)")
_DSN_PASSWORD = re.compile(r"(?P<prefix>\w+(?:\+\w+)?://[^:/\s]+:)(?P<password>[^@/\s]+)(?=@)")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")


class SecretRedactor:
    def redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: MASK if key.lower() in SECRET_KEYS else self.redact(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.redact(item) for item in value]
        if isinstance(value, str):
            text = _BEARER.sub(f"Bearer {MASK}", value)
            text = _KEY_VALUE.sub(lambda match: f"{match.group(1)}={MASK}", text)
            return _DSN_PASSWORD.sub(lambda match: f"{match.group('prefix')}{MASK}", text)
        return value


redactor = SecretRedactor()
