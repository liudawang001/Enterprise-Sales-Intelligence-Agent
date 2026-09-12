from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthMode(StrEnum):
    DISABLED = "disabled"
    JWT = "jwt"


class DatabaseSettings(BaseModel):
    url: str
    checkpoint_url: str
    pool_size: int
    max_overflow: int
    pool_timeout: float


class RedisSettings(BaseModel):
    url: str
    required: bool
    max_connections: int


class AuthSettings(BaseModel):
    mode: AuthMode
    issuer: str
    audience: str
    jwks_url: str
    algorithms: list[str]


class RuntimeSettings(BaseModel):
    checkpointer: str
    lease_seconds: int
    heartbeat_seconds: int
    shutdown_grace_seconds: int
    worker_id: str


class ObservabilitySettings(BaseModel):
    langfuse_enabled: bool
    langfuse_host: str
    capture_content: bool


class ExportSettings(BaseModel):
    backend: str
    directory: str
    bucket: str
    endpoint_url: str
    signed_url_ttl_seconds: int


class Settings(BaseSettings):
    """Flat environment contract with typed, grouped runtime views.

    Flat names keep the existing Phase 1-7 configuration compatible while the
    grouped properties give infrastructure code explicit ownership boundaries.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    service_name: str = "enterprise-sales-intelligence-agent"
    allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sales_intelligence"
    checkpoint_database_url: str = ""
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=5, ge=0)
    database_pool_timeout: float = Field(default=30.0, gt=0)

    graph_checkpointer: str = "memory"
    run_lease_seconds: int = Field(default=60, ge=5)
    run_heartbeat_seconds: int = Field(default=15, ge=1)
    shutdown_grace_seconds: int = Field(default=30, ge=1)
    worker_id: str = ""

    redis_url: str = "redis://localhost:6379/0"
    redis_required: bool = False
    redis_max_connections: int = Field(default=20, ge=1)
    cache_ttl_region_seconds: int = Field(default=604800, ge=1)
    cache_ttl_enterprise_seconds: int = Field(default=86400, ge=1)
    cache_ttl_map_seconds: int = Field(default=86400, ge=1)
    cache_ttl_web_search_seconds: int = Field(default=21600, ge=1)
    cache_ttl_rag_seconds: int = Field(default=3600, ge=1)
    provider_rate_limit_fail_safe: bool = True
    inbound_rate_limit_fallback: bool = True

    auth_mode: AuthMode = AuthMode.DISABLED
    auth_issuer: str = ""
    auth_audience: str = ""
    auth_jwks_url: str = ""
    auth_algorithms: str = "RS256"

    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_host: str = "https://cloud.langfuse.com"
    observability_capture_content: bool = False

    export_storage_backend: str = "local"
    export_dir: str = "data/exports"
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: SecretStr = SecretStr("")
    export_signed_url_ttl_seconds: int = Field(default=300, ge=30, le=3600)

    upload_max_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)
    upload_max_pages: int = Field(default=500, ge=1)
    checkpoint_retention_days: int = Field(default=30, ge=1)
    trace_retention_days: int = Field(default=14, ge=1)
    export_retention_days: int = Field(default=30, ge=1)
    task_event_retention_days: int = Field(default=30, ge=1)
    provider_raw_retention_days: int = Field(default=7, ge=0)

    # Phase 1-7 compatibility settings.
    llm_provider: str = "openai_compatible"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    embedding_provider: str = "huggingface"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024
    reranker_provider: str = "bge"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    rag_dense_top_k: int = 20
    rag_sparse_top_k: int = 20
    rag_fusion_top_k: int = 12
    rag_rerank_top_k: int = 6
    rag_min_evidence_score: float = 0.01
    rag_chunk_size: int = 900
    rag_chunk_overlap: int = 120
    rag_debug: bool = False
    rule_debug: bool = False
    model_suggestions_enabled: bool = False
    upload_dir: str = "data/uploads"
    enterprise_provider: str = "fake"
    enterprise_api_base_url: str = ""
    enterprise_api_key: str = ""
    map_provider: str = "fake"
    amap_api_key: str = ""
    web_search_provider: str = "fake"
    tavily_api_key: str = ""
    web_fetch_provider: str = "fake"
    firecrawl_api_key: str = ""
    research_max_tool_calls: int = 300
    research_max_web_searches: int = 80
    research_max_web_pages: int = 120
    research_max_candidates: int = 300
    research_max_retries: int = 3
    research_max_expansion_rounds: int = 2
    research_max_pages_per_company: int = 4
    research_discovery_multiplier: int = 4
    research_batch_size: int = 10
    research_enterprise_concurrency: int = 5
    research_map_concurrency: int = 5
    research_web_search_concurrency: int = 8
    research_web_fetch_concurrency: int = 4
    verification_max_extra_calls: int = 100
    verification_max_calls_per_entity: int = 3
    verification_max_rounds: int = 1
    delivery_max_page_size: int = 100

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        env = self.app_env.lower()
        if env in {"production", "prod"}:
            if self.auth_mode == AuthMode.DISABLED:
                raise ValueError("AUTH_MODE=disabled is forbidden in production")
            if self.graph_checkpointer != "postgres":
                raise ValueError("GRAPH_CHECKPOINTER=postgres is required in production")
            if not self.auth_issuer or not self.auth_audience or not self.auth_jwks_url:
                raise ValueError("JWT issuer, audience and JWKS URL are required in production")
            if "postgres:postgres@" in self.database_url:
                raise ValueError("default database credentials are forbidden in production")
        if self.run_heartbeat_seconds >= self.run_lease_seconds:
            raise ValueError("RUN_HEARTBEAT_SECONDS must be lower than RUN_LEASE_SECONDS")
        for name, value in {
            "DATABASE_URL": self.database_url,
            "REDIS_URL": self.redis_url,
        }.items():
            parsed = urlparse(value.replace("postgresql+asyncpg", "postgresql"))
            if not parsed.scheme or not parsed.hostname:
                raise ValueError(f"{name} is invalid")
        if self.export_storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("S3_BUCKET is required for S3 export storage")
        return self

    @property
    def database(self) -> DatabaseSettings:
        return DatabaseSettings(
            url=self.database_url,
            checkpoint_url=self.checkpoint_database_url or self.database_url,
            pool_size=self.database_pool_size,
            max_overflow=self.database_max_overflow,
            pool_timeout=self.database_pool_timeout,
        )

    @property
    def redis(self) -> RedisSettings:
        return RedisSettings(
            url=self.redis_url, required=self.redis_required, max_connections=self.redis_max_connections
        )

    @property
    def auth(self) -> AuthSettings:
        return AuthSettings(
            mode=self.auth_mode,
            issuer=self.auth_issuer,
            audience=self.auth_audience,
            jwks_url=self.auth_jwks_url,
            algorithms=[v.strip() for v in self.auth_algorithms.split(",") if v.strip()],
        )

    @property
    def runtime(self) -> RuntimeSettings:
        return RuntimeSettings(
            checkpointer=self.graph_checkpointer,
            lease_seconds=self.run_lease_seconds,
            heartbeat_seconds=self.run_heartbeat_seconds,
            shutdown_grace_seconds=self.shutdown_grace_seconds,
            worker_id=self.worker_id,
        )

    @property
    def observability(self) -> ObservabilitySettings:
        return ObservabilitySettings(
            langfuse_enabled=self.langfuse_enabled,
            langfuse_host=self.langfuse_host,
            capture_content=self.observability_capture_content,
        )

    @property
    def exports(self) -> ExportSettings:
        return ExportSettings(
            backend=self.export_storage_backend,
            directory=self.export_dir,
            bucket=self.s3_bucket,
            endpoint_url=self.s3_endpoint_url,
            signed_url_ttl_seconds=self.export_signed_url_ttl_seconds,
        )

    @property
    def cors_origins(self) -> list[str]:
        return [value.strip() for value in self.allowed_origins.split(",") if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
