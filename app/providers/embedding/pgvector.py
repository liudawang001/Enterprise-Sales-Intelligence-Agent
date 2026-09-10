from typing import Any


class PGVectorStoreFactory:
    """Lazy PGVectorStore factory; no database connection is made at import time."""

    def __init__(self, connection: str, embedding: Any, *, collection_name: str = "knowledge_chunks") -> None:
        self.connection = connection
        self.embedding = embedding
        self.collection_name = collection_name

    async def create(self) -> Any:
        from langchain_postgres import PGEngine, PGVectorStore
        engine = PGEngine.from_connection_string(url=self.connection)
        await engine.ainit_vectorstore_table(
            table_name=self.collection_name,
            vector_size=1024,
            id_column="id",
            content_column="content",
            embedding_column="embedding",
            metadata_columns=["document_id", "chunk_type", "page_start", "page_end", "section_path"],
            metadata_json_column="metadata",
            overwrite_existing=False,
        )
        return await PGVectorStore.create(
            embedding_service=self.embedding,
            engine=engine,
            table_name=self.collection_name,
            id_column="id",
            content_column="content",
            embedding_column="embedding",
            metadata_columns=["document_id", "chunk_type", "page_start", "page_end", "section_path"],
            metadata_json_column="metadata",
        )
