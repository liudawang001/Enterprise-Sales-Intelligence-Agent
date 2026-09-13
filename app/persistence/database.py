from collections.abc import AsyncIterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker


def sync_database_url(database_url: str) -> str:
    """Return the psycopg URL used by synchronous graph repositories."""

    return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


def create_sync_database_engine(
    database_url: str,
    *,
    echo: bool = False,
    pool_size: int = 5,
    max_overflow: int = 5,
    pool_timeout: float = 30.0,
) -> Engine:
    return create_engine(
        sync_database_url(database_url),
        echo=echo,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
    )


def create_sync_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def create_database_engine(
    database_url: str,
    *,
    echo: bool = False,
    pool_size: int = 5,
    max_overflow: int = 5,
    pool_timeout: float = 30.0,
) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_scope(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        async with session.begin():
            yield session
