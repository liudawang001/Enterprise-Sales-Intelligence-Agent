from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sales_intelligence"
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
