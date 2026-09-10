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
        return await PGVectorStore.create(embedding_service=self.embedding, engine=engine, table_name=self.collection_name)
