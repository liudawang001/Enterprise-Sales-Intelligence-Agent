from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ExecutionRunStatus(StrEnum):
    CREATED = "CREATED"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    WAITING_INTERRUPT = "WAITING_INTERRUPT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"
    RECOVERABLE = "RECOVERABLE"


class ExecutionRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str
    thread_id: str
    workspace_id: str
    user_id: str
    task_id: str | None = None
    task_version: int | None = None
    status: ExecutionRunStatus = ExecutionRunStatus.CREATED
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    fence_token: int = 0
    trace_id: str | None = None
    response_data: dict[str, Any] | None = None
    error_code: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    heartbeat_at: datetime | None = None
    finished_at: datetime | None = None


class RunAlreadyClaimedError(RuntimeError):
    def __init__(self, thread_id: str) -> None:
        super().__init__("RUN_ALREADY_CLAIMED")
        self.thread_id = thread_id
