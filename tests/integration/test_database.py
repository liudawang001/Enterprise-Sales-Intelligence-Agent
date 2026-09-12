import os

import pytest
from sqlalchemy import inspect, text

from app.domain.task import TaskPatch
from app.persistence.database import create_database_engine, create_session_factory
from app.repositories.task_repository import TaskRepository


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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_has_phase5_verification_tables() -> None:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    engine = create_database_engine(url)
    try:
        async with engine.connect() as connection:
            tables = set(
                await connection.run_sync(
                    lambda sync_connection: inspect(sync_connection).get_table_names()
                )
            )
        assert {
            "canonical_enterprises",
            "enterprise_candidate_links",
            "enterprise_relations",
            "enterprise_locations",
            "verification_runs",
            "enterprise_evidence",
            "resolved_fields",
            "verified_enterprise_profiles",
            "scoring_profiles",
            "lead_scores",
            "verified_lead_sets",
        } <= tables
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_has_phase6_task_control_tables() -> None:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    engine = create_database_engine(url)
    try:
        async with engine.connect() as connection:
            tables = set(await connection.run_sync(lambda sync_connection: inspect(sync_connection).get_table_names()))
        assert {"lead_tasks", "lead_task_versions", "task_mutations", "task_execution_snapshots", "task_reexecution_plans"} <= tables
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_has_phase7_delivery_tables() -> None:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    engine = create_database_engine(url)
    try:
        async with engine.connect() as connection:
            tables = set(
                await connection.run_sync(
                    lambda sync_connection: inspect(sync_connection).get_table_names()
                )
            )
        assert {"delivery_snapshots", "exports"} <= tables
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_task_versions_are_append_only() -> None:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    engine = create_database_engine(url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            repository = TaskRepository(session)
            task = await repository.create_task("phase6-integration")
            updated = await repository.apply_patch(task.task_id, TaskPatch(business="集团V网", region="上海松江", target_count=30), base_version=1)
            versions = await repository.list_versions(task.task_id)
            assert updated.version == 2
            assert [item.version for item in versions] == [1, 2]
            assert versions[0].target_count is None
    finally:
        await engine.dispose()
