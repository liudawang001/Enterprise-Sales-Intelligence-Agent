"""Run a minimal, secret-safe DashScope Rerank smoke test."""

from __future__ import annotations

import asyncio

from app.knowledge.rerank.factory import build_reranker
from app.knowledge.retrieval.models import RetrievalHit
from app.settings.production import get_settings


async def main() -> None:
    settings = get_settings()
    reranker = build_reranker(settings)
    if getattr(reranker, "provider", None) != "dashscope":
        raise SystemExit("RERANKER_PROVIDER must be dashscope for this smoke test")
    hits = [
        RetrievalHit(chunk_id="smoke-0", document_id="smoke-doc", content="企业专线适合有跨区域组网需求的企业客户。", page_start=1, page_end=1, metadata={}),
        RetrievalHit(chunk_id="smoke-1", document_id="smoke-doc", content="今天天气晴朗，适合户外活动。", page_start=1, page_end=1, metadata={}),
    ]
    ranked = await reranker.rerank("企业专线适合什么客户？", hits, top_k=2)
    if not ranked or ranked[0].chunk_id != "smoke-0":
        raise SystemExit("unexpected rerank ordering")
    print(f"provider=dashscope model={settings.reranker_model} profile={reranker.profile_version} returned={len(ranked)} tokens={reranker.last_usage.total_tokens}")


if __name__ == "__main__":
    asyncio.run(main())
