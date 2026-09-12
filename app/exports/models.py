from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class ExportStatus(StrEnum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ExportSpec(BaseModel):
    task_id: str
    task_version: int = Field(ge=1)
    source_lead_set_id: str
    source_score_set_id: str
    format: Literal["XLSX"] = "XLSX"
    target_count: int | None = Field(default=None, ge=1)
    fields: list[str]
    include_task_summary: bool = True
    include_score_breakdown: bool = True
    include_evidence_summary: bool = True
    include_conflicts: bool = True
    filename: str | None = None

    @field_validator("fields")
    @classmethod
    def fields_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("EXPORT_FIELDS_REQUIRED")
        return value


class CreateExportRequest(BaseModel):
    task_id: str
    task_version: int | None = Field(default=None, ge=1)
    snapshot_id: str | None = None
    target_count: int | None = Field(default=None, ge=1)
    fields: list[str] = Field(
        default_factory=lambda: [
            "rank",
            "enterprise_name",
            "industry",
            "lead_score",
            "verification_status",
            "recommendation_reason",
        ]
    )
    include_task_summary: bool = True
    include_score_breakdown: bool = True
    include_evidence_summary: bool = True
    include_conflicts: bool = True
    filename: str | None = None


class ExportJob(BaseModel):
    export_id: str = Field(default_factory=_id)
    snapshot_id: str
    task_id: str
    workspace_id: str = "local"
    task_version: int
    status: ExportStatus = ExportStatus.PENDING
    format: str = "XLSX"
    requested_fields: list[str]
    row_count: int | None = None
    artifact_path: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    sha256: str | None = None
    request_hash: str
    created_at: datetime = Field(default_factory=_now)
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class StoredExport(BaseModel):
    artifact_path: str
    file_name: str
    file_size: int
    sha256: str
