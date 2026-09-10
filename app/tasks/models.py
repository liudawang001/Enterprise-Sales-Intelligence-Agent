from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.domain.task import LeadTask


class TaskReference(BaseModel):
    explicit_task_id: str | None = None
    business_hint: str | None = None
    ordinal_hint: str | None = None
    use_active_task: bool = False
    confidence: float = Field(default=0.0, ge=0, le=1)


class TaskReferenceStatus(StrEnum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


class TaskCandidate(BaseModel):
    task_id: str
    business: str | None = None
    region: str | None = None
    version: int


class TaskReferenceResolution(BaseModel):
    status: TaskReferenceStatus
    task_id: str | None = None
    reference: TaskReference
    candidates: list[TaskCandidate] = Field(default_factory=list)
    reason: str


class TaskVersion(BaseModel):
    version_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    version: int
    parent_version: int | None = None
    business: str | None = None
    region: str | None = None
    target_count: int | None = None
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    export_fields: list[str] = Field(default_factory=list)
    source_message_id: str | None = None
    mutation_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_task(
        cls,
        task: LeadTask,
        *,
        parent_version: int | None = None,
        mutation_id: str | None = None,
        source_message_id: str | None = None,
    ) -> TaskVersion:
        return cls(
            task_id=task.task_id,
            version=task.version,
            parent_version=parent_version,
            business=task.business,
            region=task.region,
            target_count=task.target_count,
            constraints=task.constraints,
            required_fields=task.required_fields,
            export_fields=task.export_fields,
            source_message_id=source_message_id or task.source_message_id,
            mutation_id=mutation_id,
        )
