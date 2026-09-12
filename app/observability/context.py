from __future__ import annotations

from contextvars import ContextVar, Token

from pydantic import BaseModel


class RequestContext(BaseModel):
    request_id: str
    trace_id: str
    principal: object | None = None
    thread_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    fence_token: int | None = None


_request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def get_request_context() -> RequestContext | None:
    return _request_context.get()


def set_request_context(value: RequestContext) -> Token:
    return _request_context.set(value)


def reset_request_context(token: Token) -> None:
    _request_context.reset(token)
