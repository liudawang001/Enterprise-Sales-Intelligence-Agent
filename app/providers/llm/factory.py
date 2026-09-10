from typing import Any


def create_chat_model(*, provider: str, model: str, api_key: str = "", base_url: str = "") -> Any:
    if not api_key or not model:
        from app.providers.llm.fake import FakeChatModel
        return FakeChatModel()
    if provider == "openai_compatible":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=api_key, base_url=base_url or None)
    from app.providers.llm.fake import FakeChatModel
    return FakeChatModel()
