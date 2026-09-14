from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class ChatModelProtocol(Protocol):
    """Small provider-neutral surface used by graph services."""

    def answer(self, question: str, hits: list[Any]) -> str: ...

    def invoke_text(self, prompt: str, *, metadata: dict[str, Any] | None = None) -> str: ...

    async def ainvoke_text(self, prompt: str, *, metadata: dict[str, Any] | None = None) -> str: ...

    def structured(self, schema: type[ModelT], prompt: str, *, metadata: dict[str, Any] | None = None) -> ModelT: ...

    async def astructured(
        self, schema: type[ModelT], prompt: str, *, metadata: dict[str, Any] | None = None
    ) -> ModelT: ...
