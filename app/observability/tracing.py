from __future__ import annotations

import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class LangfuseTracing:
    """Fail-open Langfuse v4 facade using its OpenTelemetry observation API."""

    def __init__(self, settings) -> None:
        self.settings = settings
        self.client = None
        self.status = "UNKNOWN"

    async def start(self) -> None:
        if not self.settings.langfuse_enabled:
            self.status = "UNKNOWN"
            return
        try:
            from langfuse import Langfuse

            self.client = Langfuse(
                public_key=self.settings.langfuse_public_key,
                secret_key=self.settings.langfuse_secret_key.get_secret_value(),
                base_url=self.settings.langfuse_host,
            )
            self.status = "UP"
        except Exception:
            self.status = "DEGRADED"
            logger.warning("OBSERVABILITY_UNAVAILABLE", extra={"error_code": "OBSERVABILITY_UNAVAILABLE"})

    @asynccontextmanager
    async def observation(self, name: str, *, metadata: dict | None = None, input_data=None):
        if not self.client:
            yield None
            return
        kwargs = {"name": name, "metadata": metadata or {}}
        if self.settings.observability_capture_content:
            kwargs["input"] = input_data
        try:
            manager = self.client.start_as_current_observation(**kwargs)
            observation = manager.__enter__()
        except Exception:
            logger.warning("OBSERVABILITY_UNAVAILABLE", extra={"error_code": "OBSERVABILITY_UNAVAILABLE"})
            yield None
            return
        try:
            yield observation
        finally:
            try:
                manager.__exit__(None, None, None)
            except Exception:
                logger.warning("OBSERVABILITY_UNAVAILABLE", extra={"error_code": "OBSERVABILITY_UNAVAILABLE"})

    async def close(self) -> None:
        if self.client:
            try:
                self.client.flush()
                self.client.shutdown()
            except Exception:
                logger.warning("OBSERVABILITY_UNAVAILABLE", extra={"error_code": "OBSERVABILITY_UNAVAILABLE"})
