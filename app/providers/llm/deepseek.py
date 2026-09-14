from __future__ import annotations

from threading import Lock, Semaphore
from time import monotonic
from typing import Any, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.observability.metrics import metrics
from app.observability.redaction import SecretRedactor

ModelT = TypeVar("ModelT", bound=BaseModel)


class DeepSeekProviderError(RuntimeError):
    """Normalized error raised by the real DeepSeek provider."""


class DeepSeekChatModel:
    """DeepSeek OpenAI-compatible chat model with text and JSON-schema paths."""

    provider = "deepseek"

    def __init__(
        self,
        *,
        model: str = "deepseek-flash",
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        timeout: float = 60.0,
        max_retries: int = 2,
        reasoning_effort: str | None = None,
        thinking_type: str = "disabled",
        max_completion_tokens: int | None = None,
        max_concurrency: int = 8,
        circuit_failure_threshold: int = 3,
        circuit_open_seconds: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("LLM_API_KEY is required for DeepSeek")
        if model != "deepseek-flash":
            raise ValueError("LLM_MODEL must be deepseek-flash for DeepSeek provider")
        if base_url.rstrip("/") != "https://api.deepseek.com":
            raise ValueError("LLM_BASE_URL must be https://api.deepseek.com for DeepSeek provider")
        self.model = model
        self._redactor = SecretRedactor()
        self._semaphore = Semaphore(max(1, max_concurrency))
        self._circuit_lock = Lock()
        self._circuit_failures = 0
        self._circuit_opened_at = 0.0
        self._circuit_failure_threshold = max(1, circuit_failure_threshold)
        self._circuit_open_seconds = max(0.1, circuit_open_seconds)
        extra_body = None
        if thinking_type and thinking_type != "disabled":
            extra_body = {"thinking": {"type": thinking_type}}
        self._chat = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            max_retries=max_retries,
            reasoning_effort=reasoning_effort or None,
            max_completion_tokens=max_completion_tokens,
            extra_body=extra_body,
        )

    @staticmethod
    def _content(message: Any) -> str:
        content = getattr(message, "content", message)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in content)
        return str(content or "")

    def invoke_text(self, prompt: str, *, metadata: dict[str, Any] | None = None) -> str:
        started = monotonic()
        self._guard_open()
        self._semaphore.acquire()
        metrics.add("llm_calls_total", provider=self.provider, operation=str((metadata or {}).get("operation", "text")))
        try:
            response = self._chat.invoke([HumanMessage(content=prompt)], config={"metadata": metadata or {}})
            text = self._content(response).strip()
            if not text:
                raise DeepSeekProviderError("DEEPSEEK_EMPTY_RESPONSE")
            self._record_success()
            return text
        except DeepSeekProviderError:
            raise
        except Exception as exc:  # provider SDK exceptions vary by version
            metrics.add(
                "llm_errors_total",
                provider=self.provider,
                operation=str((metadata or {}).get("operation", "text")),
            )
            self._record_failure()
            raise DeepSeekProviderError(self._redactor.redact(str(exc))) from exc
        finally:
            self._semaphore.release()
            metrics.add("llm_request_duration_seconds", monotonic() - started, provider=self.provider)

    async def ainvoke_text(self, prompt: str, *, metadata: dict[str, Any] | None = None) -> str:
        started = monotonic()
        self._guard_open()
        self._semaphore.acquire()
        metrics.add("llm_calls_total", provider=self.provider, operation=str((metadata or {}).get("operation", "text")))
        try:
            response = await self._chat.ainvoke([HumanMessage(content=prompt)], config={"metadata": metadata or {}})
            text = self._content(response).strip()
            if not text:
                raise DeepSeekProviderError("DEEPSEEK_EMPTY_RESPONSE")
            self._record_success()
            return text
        except DeepSeekProviderError:
            raise
        except Exception as exc:
            metrics.add(
                "llm_errors_total",
                provider=self.provider,
                operation=str((metadata or {}).get("operation", "text")),
            )
            self._record_failure()
            raise DeepSeekProviderError(self._redactor.redact(str(exc))) from exc
        finally:
            self._semaphore.release()
            metrics.add("llm_request_duration_seconds", monotonic() - started, provider=self.provider)

    def structured(self, schema: type[ModelT], prompt: str, *, metadata: dict[str, Any] | None = None) -> ModelT:
        started = monotonic()
        operation = str((metadata or {}).get("operation", "structured"))
        metrics.add("llm_calls_total", provider=self.provider, operation=operation)
        self._guard_open()
        self._semaphore.acquire()
        try:
            runnable = self._chat.with_structured_output(schema, method="json_mode")
            result = runnable.invoke(
                [
                    SystemMessage(content="Return valid json only. Do not add markdown fences."),
                    HumanMessage(content=prompt),
                ],
                config={"metadata": metadata or {}},
            )
            validated = schema.model_validate(result)
            self._record_success()
            return validated
        except Exception as exc:
            metrics.add("llm_errors_total", provider=self.provider, operation=operation)
            self._record_failure()
            raise DeepSeekProviderError(self._redactor.redact(str(exc))) from exc
        finally:
            self._semaphore.release()
            metrics.add("llm_request_duration_seconds", monotonic() - started, provider=self.provider)

    async def astructured(self, schema: type[ModelT], prompt: str, *, metadata: dict[str, Any] | None = None) -> ModelT:
        started = monotonic()
        operation = str((metadata or {}).get("operation", "structured"))
        metrics.add("llm_calls_total", provider=self.provider, operation=operation)
        self._guard_open()
        self._semaphore.acquire()
        try:
            runnable = self._chat.with_structured_output(schema, method="json_mode")
            result = await runnable.ainvoke(
                [
                    SystemMessage(content="Return valid json only. Do not add markdown fences."),
                    HumanMessage(content=prompt),
                ],
                config={"metadata": metadata or {}},
            )
            validated = schema.model_validate(result)
            self._record_success()
            return validated
        except Exception as exc:
            metrics.add("llm_errors_total", provider=self.provider, operation=operation)
            self._record_failure()
            raise DeepSeekProviderError(self._redactor.redact(str(exc))) from exc
        finally:
            self._semaphore.release()
            metrics.add("llm_request_duration_seconds", monotonic() - started, provider=self.provider)

    def answer(self, question: str, hits: list[Any]) -> str:
        evidence = []
        for index, hit in enumerate(hits, start=1):
            evidence.append(
                f"[{index}] chunk_id={getattr(hit, 'chunk_id', '')} "
                f"document_id={getattr(hit, 'document_id', '')} "
                f"pages={getattr(hit, 'page_start', '')}-{getattr(hit, 'page_end', '')}\n"
                f"{getattr(hit, 'content', '')}"
            )
        prompt = (
            "You are a grounded enterprise sales knowledge assistant. Answer in Chinese. "
            "Use only the supplied evidence; if it is insufficient, say so explicitly. "
            "Every factual claim must include one or more citation markers such as [1].\n\n"
            f"Question: {question}\nEvidence:\n" + "\n\n".join(evidence)
        )
        return self.invoke_text(prompt, metadata={"operation": "business_qa"})

    def with_structured_output(self, schema: type[ModelT]):
        """Compatibility hook for existing LangChain-oriented services."""
        return self._chat.with_structured_output(schema, method="json_mode")

    def _guard_open(self) -> None:
        with self._circuit_lock:
            if self._circuit_opened_at and monotonic() - self._circuit_opened_at < self._circuit_open_seconds:
                raise DeepSeekProviderError("LLM_CIRCUIT_OPEN")
            if self._circuit_opened_at:
                self._circuit_opened_at = 0.0

    def _record_success(self) -> None:
        with self._circuit_lock:
            self._circuit_failures = 0
            self._circuit_opened_at = 0.0

    def _record_failure(self) -> None:
        with self._circuit_lock:
            self._circuit_failures += 1
            if self._circuit_failures >= self._circuit_failure_threshold:
                self._circuit_opened_at = monotonic()
