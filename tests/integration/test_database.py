import os

import pytest
from sqlalchemy import text

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
