"""Rebuild knowledge vectors for the active embedding profile.

Examples:
  python -m scripts.reindex_knowledge --dry-run
  python -m scripts.reindex_knowledge --document-id <uuid>
"""

from __future__ import annotations

import argparse
import asyncio
import math
from uuid import UUID

from app.agent.dependencies import build_postgres_dependencies
from app.providers.embedding.factory import build_embedding_provider
from app.settings.production import get_settings
from app.persistence.database import create_sync_database_engine, create_sync_session_factory


def estimate_tokens(text: str) -> int:
    # Conservative approximation for a dry-run cost estimate; provider usage is
    # authoritative after execution.
    return max(1, math.ceil(len(text) / 2.5))


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    embedding = build_embedding_provider(settings)
    if not settings.database_url.startswith("postgres"):
        raise RuntimeError("DATABASE_URL must point to PostgreSQL for reindex")
    engine = create_sync_database_engine(settings.database_url, pool_size=settings.database_pool_size, max_overflow=settings.database_max_overflow, pool_timeout=settings.database_pool_timeout)
    repository = build_postgres_dependencies(settings, create_sync_session_factory(engine)).knowledge_service.repository
    documents = repository.list_documents()
    profile = args.profile or settings.embedding_profile_version
    selected = []
    for document in documents:
        if args.document_id and document.id != UUID(args.document_id):
            continue
        if args.resume and document.embedding_profile_version == profile and document.status.value == "READY":
            continue
        selected.append(document)
    chunks = sum(repository.count_chunks(doc.id) for doc in selected)
    token_estimate = sum(estimate_tokens(chunk.content) for doc in selected for chunk in repository.list_chunks(doc.id))
    cost = token_estimate / 1000 * 0.0005
    print(f"profile={profile} documents={len(selected)} chunks={chunks} estimated_tokens={token_estimate} estimated_cost_rmb={cost:.6f}")
    if args.dry_run:
        engine.dispose()
        return 0
    from app.knowledge.ingestion.service import DocumentIngestionService
    service = DocumentIngestionService(repository, embedding=embedding)
    failures = 0
    for document in selected:
        try:
            result = await service.reindex(document.id)
            if result.status.value != "READY":
                failures += 1
                print(f"failed document={document.id} error={result.error_message or 'unknown'}")
        except Exception as exc:
            failures += 1
            print(f"failed document={document.id} error={type(exc).__name__}")
    engine.dispose()
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="")
    parser.add_argument("--document-id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
