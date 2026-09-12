from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agent.enums import TaskStage, TaskStatus


class ConstraintPatch(BaseModel):
    field: str
    operation: Literal["ADD", "UPDATE", "REMOVE", "CLEAR"]
    operator: str | None = None
    value: Any = None
    constraint_type: str | None = None


class TaskPatch(BaseModel):
    business: str | None = None
    region: str | None = None
    target_count: int | None = None
    constraints: list[ConstraintPatch] = Field(default_factory=list)
    required_fields: list[str] | None = None
    export_fields: list[str] | None = None


class LeadTask(BaseModel):
    task_id: str
    session_id: str
    workspace_id: str = "local"
    business: str | None = None
    region: str | None = None
    target_count: int | None = None
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    export_fields: list[str] = Field(default_factory=list)
    stage: TaskStage
    status: TaskStatus
    version: int = 1
    source_message_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Lead(BaseModel):
    company_name: str
    industry: str | None = None
    region: str | None = None
    phone: str | None = None
    address: str | None = None
    score: float | None = None
    recommendation_reason: str | None = None
    office_count: int | None = None
    employee_count: int | None = None
    member_count: int | None = None
    branch_count: int | None = None
    locations: list[str] = Field(default_factory=list)
    company_scale: str | None = None
    company_status: str | None = None
    existing_products: list[str] = Field(default_factory=list)
    cross_region_presence: bool = False
