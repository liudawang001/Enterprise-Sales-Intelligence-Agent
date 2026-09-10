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
    upload_dir: str = "data/uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
