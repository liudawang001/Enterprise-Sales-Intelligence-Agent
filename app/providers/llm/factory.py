from typing import Any


def create_chat_model(
    *,
    provider: str,
    model: str,
    api_key: str = "",
    base_url: str = "",
    timeout: float = 60.0,
    max_retries: int = 2,
    reasoning_effort: str = "",
    thinking_type: str = "disabled",
    max_completion_tokens: int | None = None,
    max_concurrency: int = 8,
    circuit_failure_threshold: int = 3,
    circuit_open_seconds: float = 30.0,
) -> Any:
    provider = (provider or "").lower().strip()
    if provider in {"fake", "deterministic_fake"}:
        from app.providers.llm.fake import FakeChatModel
        return FakeChatModel()
    if provider == "deepseek":
        from app.providers.llm.deepseek import DeepSeekChatModel

        return DeepSeekChatModel(
            model=model or "deepseek-flash",
            api_key=api_key,
            base_url=base_url or "https://api.deepseek.com",
            timeout=timeout,
            max_retries=max_retries,
            reasoning_effort=reasoning_effort or None,
            thinking_type=thinking_type,
            max_completion_tokens=max_completion_tokens,
            max_concurrency=max_concurrency,
            circuit_failure_threshold=circuit_failure_threshold,
            circuit_open_seconds=circuit_open_seconds,
        )
    if provider == "openai_compatible":
        if not api_key or not model:
            from app.providers.llm.fake import FakeChatModel
            return FakeChatModel()
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url or None,
            timeout=timeout,
            max_retries=max_retries,
            reasoning_effort=reasoning_effort or None,
            max_completion_tokens=max_completion_tokens,
        )
    raise ValueError(f"LLM_PROVIDER_UNSUPPORTED: {provider}")
