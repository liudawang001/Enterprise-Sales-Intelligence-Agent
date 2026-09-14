from types import SimpleNamespace

from pydantic import BaseModel

from app.providers.llm.deepseek import DeepSeekChatModel, DeepSeekProviderError


class Probe(BaseModel):
    intent: str


class FakeRunnable:
    def invoke(self, messages, config=None):
        return {"intent": "GENERAL_CHAT"}

    async def ainvoke(self, messages, config=None):
        return {"intent": "GENERAL_CHAT"}


class FakeChat:
    def invoke(self, messages, config=None):
        return SimpleNamespace(content="回答 [1]")

    async def ainvoke(self, messages, config=None):
        return SimpleNamespace(content="异步回答 [1]")

    def with_structured_output(self, schema, method=None):
        assert method == "json_mode"
        return FakeRunnable()


class BrokenChat(FakeChat):
    def invoke(self, messages, config=None):
        raise RuntimeError("upstream timeout")


def _model() -> DeepSeekChatModel:
    model = DeepSeekChatModel(api_key="test-secret")
    model._chat = FakeChat()
    return model


def test_deepseek_text_path_extracts_message_content() -> None:
    assert _model().invoke_text("hello") == "回答 [1]"


def test_deepseek_structured_path_validates_pydantic_schema() -> None:
    result = _model().structured(Probe, "return json")
    assert result.intent == "GENERAL_CHAT"


def test_deepseek_circuit_opens_after_bounded_failures() -> None:
    model = DeepSeekChatModel(api_key="test-secret", circuit_failure_threshold=2, circuit_open_seconds=60)
    model._chat = BrokenChat()
    for _ in range(2):
        try:
            model.invoke_text("hello")
        except DeepSeekProviderError:
            pass
    try:
        model.invoke_text("hello")
    except DeepSeekProviderError as exc:
        assert str(exc) == "LLM_CIRCUIT_OPEN"
    else:
        raise AssertionError("circuit should reject the third call")
