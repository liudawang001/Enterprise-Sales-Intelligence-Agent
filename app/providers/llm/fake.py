from app.knowledge.retrieval.models import RetrievalHit


class FakeChatModel:
    def answer(self, question: str, hits: list[RetrievalHit]) -> str:
        if not hits:
            return "当前知识库中没有找到足够证据确认该问题。"
        parts = []
        for index, hit in enumerate(hits, start=1):
            excerpt = hit.content.strip().replace("\n", " ")
            parts.append(f"{excerpt} [{index}]")
        return "根据知识库资料：" + "；".join(parts)
