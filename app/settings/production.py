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
    socket_timeout_seconds: float
    socket_connect_timeout_seconds: float


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
    redis_socket_timeout_seconds: float = Field(default=2.0, gt=0)
    redis_socket_connect_timeout_seconds: float = Field(default=2.0, gt=0)
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
    embedding_provider: str = "fake"
    embedding_model: str = "qwen3.7-text-embedding"
    embedding_api_key: SecretStr = SecretStr("")
    dashscope_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="DASHSCOPE_API_KEY", exclude=True)
    embedding_base_url: str = ""
    embedding_dimension: int = Field(default=1024, ge=1)
    embedding_batch_size: int = Field(default=16, ge=1, le=20)
    embedding_timeout_seconds: float = Field(default=30.0, gt=0)
    embedding_connect_timeout_seconds: float = Field(default=5.0, gt=0)
    embedding_max_retries: int = Field(default=3, ge=0, le=10)
    embedding_concurrency: int = Field(default=4, ge=1)
    embedding_output_type: str = "dense"
    rag_embedding_profile: str = ""
    rag_allow_fake: bool = False
    rag_read_profile: str = ""
    reranker_provider: str = "bge"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_api_key: SecretStr = SecretStr("")
    reranker_base_url: str = ""
    reranker_timeout_seconds: float = Field(default=30.0, gt=0)
    reranker_connect_timeout_seconds: float = Field(default=5.0, gt=0)
    reranker_max_retries: int = Field(default=3, ge=0, le=10)
    reranker_return_documents: bool = False
    reranker_max_candidates: int = Field(default=12, ge=1)
    reranker_max_document_chars: int = Field(default=12000, ge=1)
    rag_reranker_profile: str = ""
    rag_reranker_read_profile: str = ""
    rag_allow_fake_reranker: bool = False
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

    @model_validator(mode="before")
    @classmethod
    def resolve_embedding_secret(cls, values):
        if isinstance(values, dict) and not values.get("embedding_api_key"):
            fallback = values.get("DASHSCOPE_API_KEY") or values.get("dashscope_api_key")
            if fallback:
                values = dict(values)
                values["embedding_api_key"] = fallback
        if isinstance(values, dict) and not values.get("reranker_api_key"):
            fallback = values.get("DASHSCOPE_API_KEY") or values.get("dashscope_api_key")
            if fallback:
                values = dict(values)
                values["reranker_api_key"] = fallback
        return values

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
            if "*" in self.cors_origins:
                raise ValueError("wildcard CORS is forbidden in production")
            if self.rag_debug or self.rule_debug:
                raise ValueError("debug output is forbidden in production")
            provider_requirements = {
                "ENTERPRISE_PROVIDER=commercial": self.enterprise_provider == "commercial",
                "ENTERPRISE_API_BASE_URL": bool(self.enterprise_api_base_url),
                "ENTERPRISE_API_KEY": bool(self.enterprise_api_key),
                "MAP_PROVIDER=amap": self.map_provider == "amap",
                "AMAP_API_KEY": bool(self.amap_api_key),
                "WEB_SEARCH_PROVIDER=tavily": self.web_search_provider == "tavily",
                "TAVILY_API_KEY": bool(self.tavily_api_key),
                "WEB_FETCH_PROVIDER=firecrawl": self.web_fetch_provider == "firecrawl",
                "FIRECRAWL_API_KEY": bool(self.firecrawl_api_key),
            }
            missing = [name for name, configured in provider_requirements.items() if not configured]
            if missing:
                raise ValueError("real provider configuration is required in production: " + ", ".join(missing))
            if self.embedding_provider.lower() in {"fake", "deterministic_fake"} or self.rag_allow_fake:
                raise ValueError("real embedding provider is required in production")
            if self.embedding_provider.lower() == "dashscope":
                if not self.embedding_api_key.get_secret_value():
                    raise ValueError("EMBEDDING_API_KEY is required for DashScope embedding")
                if not self.embedding_base_url or "{" in self.embedding_base_url or "}" in self.embedding_base_url:
                    raise ValueError("EMBEDDING_BASE_URL must be a concrete DashScope URL")
                parsed_embedding = urlparse(self.embedding_base_url)
                if parsed_embedding.scheme != "https" or not parsed_embedding.hostname or not (parsed_embedding.hostname.endswith(".aliyuncs.com") or parsed_embedding.hostname == "dashscope.aliyuncs.com"):
                    raise ValueError("EMBEDDING_BASE_URL must be an HTTPS DashScope regional URL")
                if self.embedding_model != "qwen3.7-text-embedding":
                    raise ValueError("EMBEDDING_MODEL must be qwen3.7-text-embedding")
                if self.embedding_dimension != 1024:
                    raise ValueError("EMBEDDING_DIMENSION must be 1024 for qwen3.7-text-embedding")
            if self.reranker_provider.lower() == "fake" or self.rag_allow_fake_reranker:
                raise ValueError("real reranker provider is required in production")
            if self.reranker_provider.lower() == "dashscope":
                if not self.reranker_api_key.get_secret_value():
                    raise ValueError("RERANKER_API_KEY is required for DashScope reranker")
                if not self.reranker_base_url or "{" in self.reranker_base_url or "}" in self.reranker_base_url:
                    raise ValueError("RERANKER_BASE_URL must be a concrete DashScope URL")
                parsed_reranker = urlparse(self.reranker_base_url)
                if parsed_reranker.scheme != "https" or not parsed_reranker.hostname or not (parsed_reranker.hostname.endswith(".aliyuncs.com") or parsed_reranker.hostname == "dashscope.aliyuncs.com"):
                    raise ValueError("RERANKER_BASE_URL must be an HTTPS DashScope regional URL")
                if self.reranker_model not in {"qwen3-rerank", "gte-rerank-v2", "qwen3-vl-rerank"}:
                    raise ValueError("RERANKER_MODEL is not a supported DashScope text rerank model")
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
        if self.embedding_output_type != "dense":
            raise ValueError("EMBEDDING_OUTPUT_TYPE must be dense")
        if self.embedding_provider.lower() == "dashscope" and self.embedding_dimension != 1024:
            raise ValueError("DashScope qwen3.7-text-embedding requires EMBEDDING_DIMENSION=1024")
        if self.reranker_provider.lower() == "dashscope" and self.reranker_model not in {"qwen3-rerank", "gte-rerank-v2", "qwen3-vl-rerank"}:
            raise ValueError("RERANKER_MODEL is not a supported DashScope text rerank model")
        return self

    @property
    def embedding_api_key_value(self) -> str:
        return self.embedding_api_key.get_secret_value()

    @property
    def embedding_profile_version(self) -> str:
        return self.rag_embedding_profile or f"{self.embedding_model}:{self.embedding_dimension}:v1"

    @property
    def reranker_api_key_value(self) -> str:
        return self.reranker_api_key.get_secret_value()

    @property
    def reranker_profile_version(self) -> str:
        # READ_PROFILE is the runtime-selected profile during rollout; the
        # write/profile value remains a backwards-compatible fallback.
        return self.rag_reranker_read_profile or self.rag_reranker_profile or f"{self.reranker_model}:v1"

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
            url=self.redis_url,
            required=self.redis_required,
            max_connections=self.redis_max_connections,
            socket_timeout_seconds=self.redis_socket_timeout_seconds,
            socket_connect_timeout_seconds=self.redis_socket_connect_timeout_seconds,
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
