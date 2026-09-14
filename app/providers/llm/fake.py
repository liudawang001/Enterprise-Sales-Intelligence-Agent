from pydantic import BaseModel

from app.knowledge.retrieval.models import RetrievalHit


class FakeChatModel:
    provider = "fake"

    def answer(self, question: str, hits: list[RetrievalHit]) -> str:
        if not hits:
            return "当前知识库中没有找到足够证据确认该问题。"
        parts = []
        for index, hit in enumerate(hits, start=1):
            excerpt = hit.content.strip().replace("\n", " ")
            parts.append(f"{excerpt} [{index}]")
        return "根据知识库资料：" + "；".join(parts)

    def invoke_text(self, prompt: str, *, metadata=None) -> str:
        return prompt

    async def ainvoke_text(self, prompt: str, *, metadata=None) -> str:
        return prompt

    async def astream_text(self, prompt: str, *, metadata=None):
        for index in range(0, len(prompt), 32):
            yield prompt[index : index + 32]

    def structured(self, schema: type[BaseModel], prompt: str, *, metadata=None):
        raise RuntimeError("FakeChatModel does not implement structured generation")

    async def astructured(self, schema: type[BaseModel], prompt: str, *, metadata=None):
        raise RuntimeError("FakeChatModel does not implement structured generation")
