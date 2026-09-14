"""Credentialed DeepSeek Flash smoke; reads the key only from the environment."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime

from pydantic import BaseModel

from app.providers.llm.deepseek import DeepSeekChatModel


class SmokeResult(BaseModel):
    ok: bool


def main() -> int:
    key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY")
    if not key:
        print("DEEPSEEK_API_KEY or LLM_API_KEY is required", file=sys.stderr)
        return 2
    model = DeepSeekChatModel(
        model=os.getenv("LLM_MODEL", "deepseek-flash"),
        api_key=key,
        base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
    )
    try:
        text = model.invoke_text("Reply with a short Chinese greeting. Do not include secrets.")
        structured = model.structured(
            SmokeResult,
            'Return valid json only with exactly one boolean field: {"ok": true}. The answer must be JSON.',
        )
        payload = {
            "ok": bool(text.strip()) and structured.ok,
            "model": model.model,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__, "error": "redacted"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
