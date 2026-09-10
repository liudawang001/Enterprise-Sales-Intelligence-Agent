import hashlib
import math


class DeterministicFakeEmbedding:
    def __init__(self, dimension: int = 1024) -> None:
        self.dimension = dimension

    def _embed(self, text: str) -> list[float]:
        values = [0.0] * self.dimension
        data = text.encode("utf-8")
        for index in range(0, len(data), 2):
            digest = hashlib.sha256(data[index : index + 2]).digest()
            slot = int.from_bytes(digest[:4], "big") % self.dimension
            values[slot] += 1.0
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)
