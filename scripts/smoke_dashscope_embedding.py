"""Run a minimal, secret-safe DashScope embedding smoke test.

Configure EMBEDDING_PROVIDER=dashscope, EMBEDDING_API_KEY (or
DASHSCOPE_API_KEY), and EMBEDDING_BASE_URL in the environment before running.
"""

from __future__ import annotations

import asyncio

from app.providers.embedding.factory import build_embedding_provider
from app.settings.production import get_settings


async def main() -> None:
    settings = get_settings()
    provider = build_embedding_provider(settings)
    if getattr(provider, "provider", None) != "dashscope":
        raise SystemExit("EMBEDDING_PROVIDER must be dashscope for this smoke test")
    vector = await provider.aembed_query("企业专线办理条件")
    if len(vector) != settings.embedding_dimension:
        raise SystemExit(f"unexpected vector dimension: {len(vector)}")
    print(f"provider=dashscope model={settings.embedding_model} dimension={len(vector)} profile={provider.profile_version} tokens={provider.last_usage.total_tokens}")


if __name__ == "__main__":
    asyncio.run(main())
