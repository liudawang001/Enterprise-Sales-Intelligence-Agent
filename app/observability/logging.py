from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from app.observability.context import get_request_context
from app.observability.redaction import redactor


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        context = get_request_context()
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", "enterprise-sales-intelligence-agent"),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if context:
            payload.update(
                {key: value for key, value in context.model_dump(exclude={"principal"}).items() if value is not None}
            )
        for key in ("node", "provider", "error_code", "task_version"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(redactor.redact(payload), ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
