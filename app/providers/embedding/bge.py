from typing import Any


class BGEEmbeddingProvider:
    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        self.model_name = model_name
        self._embeddings: Any = None

    def _load(self) -> Any:
        if self._embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            self._embeddings = HuggingFaceEmbeddings(model_name=self.model_name, encode_kwargs={"normalize_embeddings": True})
        return self._embeddings

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._load().embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._load().embed_query(text)
