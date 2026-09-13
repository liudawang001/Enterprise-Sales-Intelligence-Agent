from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from sqlalchemy import text

from app.agent.dependencies import build_postgres_dependencies
from app.infrastructure.cache import ProviderCache, RedisCacheService
from app.infrastructure.circuit_breaker import CircuitBreaker
from app.infrastructure.events import PostgresTaskEventRepository, TaskEventService
from app.infrastructure.rate_limit import RedisTokenBucket
from app.infrastructure.redis import RedisManager
from app.knowledge.ingestion.service import DocumentIngestionService
from app.observability.tracing import LangfuseTracing
from app.persistence.database import (
    create_database_engine,
    create_session_factory,
    create_sync_database_engine,
    create_sync_session_factory,
)
from app.runtime.graph_runtime import GraphRuntime
from app.runtime.leases import InMemoryExecutionCoordinator, PostgresExecutionCoordinator

logger = logging.getLogger(__name__)


def application_lifespan(settings):
    @asynccontextmanager
    async def lifespan(app):
        app.state.accepting_work = True
        app.state.dependency_status = {}
        app.state.redis_manager = RedisManager(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            socket_timeout=settings.redis_socket_timeout_seconds,
            socket_connect_timeout=settings.redis_socket_connect_timeout_seconds,
        )
        app.state.tracing = LangfuseTracing(settings)
        app.state.database_engine = None
        app.state.sync_database_engine = None
        graph_runtime = None
        try:
            if settings.graph_checkpointer == "postgres":
                engine = create_database_engine(
                    settings.database_url,
                    pool_size=settings.database_pool_size,
                    max_overflow=settings.database_max_overflow,
                    pool_timeout=settings.database_pool_timeout,
                )
                app.state.database_engine = engine
                async with engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
                sync_engine = create_sync_database_engine(
                    settings.database_url,
                    pool_size=settings.database_pool_size,
                    max_overflow=settings.database_max_overflow,
                    pool_timeout=settings.database_pool_timeout,
                )
                app.state.sync_database_engine = sync_engine
                with sync_engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                deps = build_postgres_dependencies(settings, create_sync_session_factory(sync_engine))
                deps.execution_coordinator = PostgresExecutionCoordinator(create_session_factory(engine))
                app.state.dependencies = deps
                app.state.knowledge_repository = deps.knowledge_service.repository
                app.state.knowledge_service = deps.knowledge_service
                app.state.ingestion_service = DocumentIngestionService(app.state.knowledge_repository)
                app.state.business_task_store = None
                app.state.event_repository = PostgresTaskEventRepository(create_session_factory(engine))
                deps.event_repository = app.state.event_repository
                app.state.dependency_status["postgres"] = "UP"
                app.state.dependency_status["checkpointer"] = "UP"
            else:
                app.state.dependencies.execution_coordinator = InMemoryExecutionCoordinator()
                app.state.business_task_store = None
                app.state.dependency_status["postgres"] = "UNKNOWN"
                app.state.dependency_status["checkpointer"] = "UP"
            try:
                await app.state.redis_manager.start()
                app.state.dependency_status["redis"] = "UP"
                app.state.inbound_limiter = RedisTokenBucket(
                    app.state.redis_manager.client, fail_open=settings.inbound_rate_limit_fallback
                )
                app.state.event_service = TaskEventService(app.state.event_repository, app.state.redis_manager.client)
                provider_cache = ProviderCache(
                    RedisCacheService(app.state.redis_manager.client),
                    {
                        "enterprise_search": settings.cache_ttl_enterprise_seconds,
                        "enterprise_profile": settings.cache_ttl_enterprise_seconds,
                        "map": settings.cache_ttl_map_seconds,
                        "web_search": settings.cache_ttl_web_search_seconds,
                        "web_fetch": settings.cache_ttl_web_search_seconds,
                    },
                )
                provider_limiter = RedisTokenBucket(
                    app.state.redis_manager.client, fail_open=not settings.provider_rate_limit_fail_safe
                )
                app.state.dependencies.research_service.configure_runtime_infrastructure(
                    cache=provider_cache, rate_limiter=provider_limiter, circuit_breaker=CircuitBreaker()
                )
            except Exception:
                app.state.dependency_status["redis"] = "DOWN" if settings.redis_required else "DEGRADED"
                logger.warning("CACHE_UNAVAILABLE", extra={"error_code": "CACHE_UNAVAILABLE"})
            app.state.event_service = TaskEventService(app.state.event_repository, app.state.redis_manager.client)
            await app.state.tracing.start()
            app.state.dependency_status["langfuse"] = app.state.tracing.status
            graph_runtime = GraphRuntime(app.state.dependencies, settings)
            app.state.graph = await graph_runtime.start()
            yield
        finally:
            app.state.accepting_work = False
            await app.state.tracing.close()
            await app.state.redis_manager.close()
            if graph_runtime is not None:
                await graph_runtime.close()
            if app.state.database_engine is not None:
                await app.state.database_engine.dispose()
            if app.state.sync_database_engine is not None:
                app.state.sync_database_engine.dispose()

    return lifespan
