from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.execution.models import ArtifactValidity, TaskExecutionSnapshot
from app.mutation.models import ReexecutionPlan, TaskMutation
from app.persistence.models.task import (
    TaskExecutionSnapshotRecord,
    TaskMutationRecord,
    TaskReexecutionPlanRecord,
)


class MutationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_mutation(self, value: TaskMutation) -> TaskMutation:
        existing = await self.session.scalar(select(TaskMutationRecord).where(TaskMutationRecord.task_id == UUID(value.task_id), TaskMutationRecord.source_message_id == value.source_message_id))
        if existing:
            return self._to_mutation(existing)
        self.session.add(TaskMutationRecord(id=UUID(value.mutation_id), task_id=UUID(value.task_id), base_version=value.base_version, target_version=value.target_version, source_message_id=value.source_message_id, patch_json=value.patch.model_dump(mode="json"), preview_json=value.preview.model_dump(mode="json") if value.preview else None, task_diff_json=value.task_diff.model_dump(mode="json") if value.task_diff else None, criteria_diff_json=value.criteria_diff.model_dump(mode="json") if value.criteria_diff else None, scope=value.scope.value if value.scope else None, reexecution_plan_id=UUID(value.reexecution_plan_id) if value.reexecution_plan_id else None, created_at=value.created_at))
        await self.session.flush()
        return value

    async def save_plan(self, value: ReexecutionPlan) -> ReexecutionPlan:
        if not await self.session.get(TaskReexecutionPlanRecord, UUID(value.plan_id)):
            self.session.add(TaskReexecutionPlanRecord(id=UUID(value.plan_id), task_id=UUID(value.task_id), base_version=value.base_version, target_version=value.next_version, original_scope=value.original_scope.value, final_scope=value.final_scope.value, start_stage=value.start_stage, steps_json=value.steps, reused_artifact_ids=value.reused_artifact_ids, invalidated_artifact_ids=value.invalidated_artifact_ids, required_fields=value.required_fields, reason_codes=value.reason_codes, reuse_decisions={key: item.value for key, item in value.reuse_decisions.items()}, status=value.status.value, escalation_reason=value.escalation_reason, estimated_external_calls=value.estimated_external_calls, created_at=value.created_at, started_at=value.started_at, finished_at=value.finished_at))
            await self.session.flush()
        return value

    @staticmethod
    def _to_mutation(record: TaskMutationRecord) -> TaskMutation:
        return TaskMutation(mutation_id=str(record.id), task_id=str(record.task_id), source_message_id=record.source_message_id, base_version=record.base_version, target_version=record.target_version, patch=record.patch_json, preview=record.preview_json, task_diff=record.task_diff_json, criteria_diff=record.criteria_diff_json, scope=record.scope, reexecution_plan_id=str(record.reexecution_plan_id) if record.reexecution_plan_id else None, created_at=record.created_at)


class ExecutionSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def promote(self, value: TaskExecutionSnapshot, *, current_task_version: int) -> bool:
        if value.task_version != current_task_version:
            value = value.model_copy(update={"is_current": False, "validity": ArtifactValidity.SUPERSEDED})
            await self.save(value)
            return False
        await self.session.execute(update(TaskExecutionSnapshotRecord).where(TaskExecutionSnapshotRecord.task_id == UUID(value.task_id), TaskExecutionSnapshotRecord.is_current.is_(True)).values(is_current=False, validity=ArtifactValidity.REUSABLE.value))
        await self.save(value.model_copy(update={"is_current": True, "validity": ArtifactValidity.CURRENT}))
        return True

    async def save(self, value: TaskExecutionSnapshot) -> TaskExecutionSnapshot:
        record = await self.session.get(TaskExecutionSnapshotRecord, UUID(value.snapshot_id))
        if not record:
            self.session.add(TaskExecutionSnapshotRecord(id=UUID(value.snapshot_id), task_id=UUID(value.task_id), task_version=value.task_version, criteria_snapshot_id=UUID(value.criteria_snapshot_id) if value.criteria_snapshot_id else None, search_plan_id=UUID(value.search_plan_id) if value.search_plan_id else None, raw_candidate_set_id=UUID(value.raw_candidate_set_id) if value.raw_candidate_set_id else None, filtered_candidate_set_id=UUID(value.filtered_candidate_set_id) if value.filtered_candidate_set_id else None, researched_candidate_set_id=UUID(value.researched_candidate_set_id) if value.researched_candidate_set_id else None, verified_lead_set_id=UUID(value.verified_lead_set_id) if value.verified_lead_set_id else None, scoring_profile_id=UUID(value.scoring_profile_id) if value.scoring_profile_id else None, lead_score_set_id=UUID(value.lead_score_set_id) if value.lead_score_set_id else None, is_current=value.is_current, validity=value.validity.value, created_at=value.created_at))
            await self.session.flush()
        return value
