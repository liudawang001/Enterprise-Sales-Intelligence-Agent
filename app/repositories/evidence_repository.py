from __future__ import annotations

import json
from copy import deepcopy
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.evidence.models import (
    Evidence,
    ResolvedField,
    VerificationRun,
    VerifiedEnterpriseProfile,
)
from app.persistence.models.verification import (
    EnterpriseEvidenceRecord,
    ResolvedFieldRecord,
    VerificationRunRecord,
    VerifiedEnterpriseProfileRecord,
)


class InMemoryEvidenceRepository:
    def __init__(self) -> None:
        self.runs: dict[str, VerificationRun] = {}
        self.evidence: dict[str, Evidence] = {}
        self.resolved_fields: dict[tuple[str, str], ResolvedField] = {}
        self.profiles: dict[str, VerifiedEnterpriseProfile] = {}

    def save_run(self, value: VerificationRun) -> VerificationRun:
        self.runs[value.verification_run_id] = deepcopy(value)
        return deepcopy(value)

    def save_evidence(self, value: Evidence) -> Evidence:
        normalized = json.dumps(
            value.normalized_value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        existing = next(
            (
                item
                for item in self.evidence.values()
                if (
                    item.enterprise_id,
                    item.field_name,
                    item.source_record_id,
                    json.dumps(
                        item.normalized_value,
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    ),
                )
                == (
                    value.enterprise_id,
                    value.field_name,
                    value.source_record_id,
                    normalized,
                )
            ),
            None,
        )
        if existing:
            self.evidence[existing.evidence_id] = deepcopy(
                value.model_copy(update={"evidence_id": existing.evidence_id})
            )
            return deepcopy(self.evidence[existing.evidence_id])
        self.evidence[value.evidence_id] = deepcopy(value)
        return deepcopy(value)

    def save_resolved_field(self, value: ResolvedField) -> ResolvedField:
        self.resolved_fields[(value.enterprise_id, value.field_name)] = deepcopy(value)
        return deepcopy(value)

    def save_profile(self, value: VerifiedEnterpriseProfile) -> VerifiedEnterpriseProfile:
        self.profiles[value.profile_id] = deepcopy(value)
        return deepcopy(value)

    def list_evidence(self, enterprise_id: str, field_name: str | None = None) -> list[Evidence]:
        return [deepcopy(item) for item in self.evidence.values() if item.enterprise_id == enterprise_id and (field_name is None or item.field_name == field_name)]

    def get_profile(self, enterprise_id: str) -> VerifiedEnterpriseProfile | None:
        values = [item for item in self.profiles.values() if item.enterprise_id == enterprise_id]
        return deepcopy(values[-1]) if values else None

    def latest_run_for_task(self, task_id: str) -> VerificationRun | None:
        values = [item for item in self.runs.values() if item.task_id == task_id]
        return deepcopy(values[-1]) if values else None


class EvidenceRepository:
    """PostgreSQL adapter for field evidence and immutable verification runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_run(self, value: VerificationRun) -> VerificationRun:
        record = await self.session.get(VerificationRunRecord, UUID(value.verification_run_id))
        fields = {
            "task_id": value.task_id,
            "candidate_set_id": UUID(value.researched_candidate_set_id),
            "resolution_run_id": UUID(value.resolution_run_id),
            "status": value.status,
            "budget_json": value.budget.model_dump(mode="json"),
            "used_budget_json": value.used_budget,
            "warnings": value.warnings,
            "started_at": value.started_at,
            "finished_at": value.finished_at,
        }
        if record:
            for key, item in fields.items():
                setattr(record, key, item)
        else:
            self.session.add(VerificationRunRecord(id=UUID(value.verification_run_id), **fields))
        await self.session.flush()
        return value

    async def save_evidence(self, value: Evidence) -> Evidence:
        record = await self.session.get(
            EnterpriseEvidenceRecord, UUID(value.evidence_id)
        )
        if not record:
            self.session.add(EnterpriseEvidenceRecord(id=UUID(value.evidence_id), enterprise_id=UUID(value.enterprise_id), field_name=value.field_name, value_json=value.value, normalized_value_json=value.normalized_value, provider=value.provider, source_type=value.source_type.value, source_record_id=UUID(value.source_record_id), source_url=value.source_url, retrieved_at=value.retrieved_at, confidence=value.confidence, extraction_method=value.extraction_method, raw_reference=value.raw_reference, stale=value.stale, created_at=value.created_at))
        else:
            record.confidence = value.confidence
            record.stale = value.stale
            record.normalized_value_json = value.normalized_value
        await self.session.flush()
        return value

    async def save_resolved_field(self, value: ResolvedField, *, verification_run_id: str) -> ResolvedField:
        record = await self.session.get(ResolvedFieldRecord, UUID(value.resolved_field_id))
        if not record:
            self.session.add(ResolvedFieldRecord(id=UUID(value.resolved_field_id), verification_run_id=UUID(verification_run_id), enterprise_id=UUID(value.enterprise_id), field_name=value.field_name, primary_value_json=value.primary_value, status=value.status.value, confidence=value.confidence, supporting_evidence_ids=value.supporting_evidence_ids, conflicting_evidence_ids=value.conflicting_evidence_ids, alternatives=value.alternatives, selection_reason=value.selection_reason, resolved_at=value.resolved_at))
            await self.session.flush()
        return value

    async def save_profile(self, value: VerifiedEnterpriseProfile) -> VerifiedEnterpriseProfile:
        if not await self.session.get(VerifiedEnterpriseProfileRecord, UUID(value.profile_id)):
            self.session.add(VerifiedEnterpriseProfileRecord(id=UUID(value.profile_id), verification_run_id=UUID(value.verification_run_id), enterprise_id=UUID(value.enterprise_id), profile_json=value.model_dump(mode="json"), status=value.status.value, evidence_coverage=value.evidence_coverage, updated_at=value.updated_at))
            await self.session.flush()
        return value
