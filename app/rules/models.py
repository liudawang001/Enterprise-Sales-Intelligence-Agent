from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class RuleSourceType(StrEnum):
    OFFICIAL_REQUIREMENT = "OFFICIAL_REQUIREMENT"
    MARKETING_RULE = "MARKETING_RULE"
    USER_REQUIREMENT = "USER_REQUIREMENT"
    MODEL_SUGGESTION = "MODEL_SUGGESTION"


class ConstraintType(StrEnum):
    HARD = "HARD"
    SOFT = "SOFT"
    INFO = "INFO"


class RuleModality(StrEnum):
    REQUIRED = "REQUIRED"
    RECOMMENDED = "RECOMMENDED"
    INFORMATIONAL = "INFORMATIONAL"


class RuleStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    EXPIRED = "EXPIRED"


class RuleResolutionStatus(StrEnum):
    INCLUDED = "INCLUDED"
    SUPPRESSED = "SUPPRESSED"
    CONFLICT = "CONFLICT"
    INVALID = "INVALID"


class RuleErrorType(StrEnum):
    RULE_EXTRACTION_FAILED = "RULE_EXTRACTION_FAILED"
    INVALID_RULE_FIELD = "INVALID_RULE_FIELD"
    INVALID_RULE_OPERATOR = "INVALID_RULE_OPERATOR"
    INVALID_RULE_VALUE = "INVALID_RULE_VALUE"
    OFFICIAL_RULE_MISSING_EVIDENCE = "OFFICIAL_RULE_MISSING_EVIDENCE"
    RULE_CONFLICT = "RULE_CONFLICT"
    CRITERIA_COMPILE_FAILED = "CRITERIA_COMPILE_FAILED"
    CRITERIA_VALIDATION_FAILED = "CRITERIA_VALIDATION_FAILED"


class RuleOperator(StrEnum):
    EQ = "EQ"
    NE = "NE"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    IN = "IN"
    NOT_IN = "NOT_IN"
    CONTAINS = "CONTAINS"
    EXISTS = "EXISTS"
    NOT_EXISTS = "NOT_EXISTS"


class RuleProvenance(BaseModel):
    source_type: RuleSourceType
    document_id: str | None = None
    chunk_id: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    source_message_id: str | None = None
    marketing_rule_id: str | None = None
    model_reasoning_summary: str | None = None
    evidence_text: str | None = None


class BusinessRule(BaseModel):
    rule_id: str = Field(default_factory=lambda: str(uuid4()))
    business_code: str
    field: str
    operator: RuleOperator
    value: Any
    value_type: str
    source_type: RuleSourceType
    constraint_type: ConstraintType
    weight: float | None = None
    confidence: float = 1.0
    rationale: str | None = None
    region: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    provenance: list[RuleProvenance] = Field(default_factory=list)
    source_message_id: str | None = None
    source_key: str | None = None
    modality: RuleModality | None = None
    status: RuleStatus = RuleStatus.ACTIVE
    resolution_status: RuleResolutionStatus = RuleResolutionStatus.INCLUDED
    suppression_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("operator", mode="before")
    @classmethod
    def operator_alias(cls, value: Any) -> Any:
        if isinstance(value, str):
            aliases = {"=": "EQ", "等于": "EQ", "至少": "GTE", ">=": "GTE", "不少于": "GTE", "大于": "GT", ">": "GT", "最多": "LTE", "不超过": "LTE", "<=": "LTE", "小于": "LT", "<": "LT", "包含": "CONTAINS"}
            return aliases.get(value.strip(), value.strip().upper())
        return value

    @field_validator("confidence")
    @classmethod
    def confidence_range(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return value

    @field_validator("weight")
    @classmethod
    def weight_range(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 1:
            raise ValueError("weight must be between 0 and 1")
        return value


class RuleEvidenceChunk(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    page_start: int | None = None
    page_end: int | None = None


class ExtractedBusinessRule(BaseModel):
    field: str
    operator: RuleOperator
    value: Any
    value_type: str | None = None
    modality: RuleModality = RuleModality.INFORMATIONAL
    confidence: float = 1.0
    rationale: str | None = None
    evidence_chunk_ids: list[str] = Field(default_factory=list)


class OfficialRuleExtractionInput(BaseModel):
    business: str
    task_requirements: dict[str, Any]
    evidence_chunks: list[RuleEvidenceChunk]


class OfficialRuleExtractionResult(BaseModel):
    rules: list[ExtractedBusinessRule] = Field(default_factory=list)
    ignored_facts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ModelSuggestion(BaseModel):
    field: str
    operator: RuleOperator
    value: Any
    rationale: str
    confidence: float
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def suggestion_confidence_range(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return value


class ModelSuggestionResult(BaseModel):
    suggestions: list[ModelSuggestion] = Field(default_factory=list)


class RuleConflictType(StrEnum):
    DUPLICATE = "DUPLICATE"
    COMPATIBLE = "COMPATIBLE"
    NARROWER = "NARROWER"
    DIRECT_CONFLICT = "DIRECT_CONFLICT"
    OFFICIAL_USER_CONFLICT = "OFFICIAL_USER_CONFLICT"
    SOFT_CONFLICT = "SOFT_CONFLICT"


class RuleConflict(BaseModel):
    conflict_id: str = Field(default_factory=lambda: str(uuid4()))
    conflict_type: RuleConflictType
    rule_ids: list[str]
    field: str
    blocking: bool
    explanation: str
    suggested_actions: list[str] = Field(default_factory=list)
