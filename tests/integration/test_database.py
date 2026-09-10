import os

import pytest
from sqlalchemy import inspect, text

from app.persistence.database import create_database_engine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_has_pgvector_extension() -> None:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    engine = create_database_engine(url)
    try:
        async with engine.connect() as connection:
            version = await connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
        assert version
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_has_phase4_research_tables() -> None:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    engine = create_database_engine(url)
    try:
        async with engine.connect() as connection:
            tables = set(await connection.run_sync(lambda sync_connection: inspect(sync_connection).get_table_names()))
        assert {"research_runs", "research_search_plans", "research_batches", "enterprise_candidates", "candidate_sets", "candidate_set_members", "research_source_records", "tool_runs"} <= tables
    finally:
        await engine.dispose()
