from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models.research import (
    CandidateSetMemberRecord,
    CandidateSetRecord,
    EnterpriseCandidateRecord,
    ResearchBatchRecord,
    ResearchRunRecord,
    ResearchSearchPlanRecord,
    ResearchSourceRecordModel,
    ToolRunRecord,
)
from app.research.models import (
    CandidateSet,
    RawEnterpriseCandidate,
    ResearchBatch,
    ResearchRun,
    SearchPlan,
    SourceRecord,
    ToolRun,
)


class ResearchRepository:
    """PostgreSQL business persistence adapter for Phase 4 research artifacts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_plan(self, value: SearchPlan) -> SearchPlan:
        record = await self.session.get(ResearchSearchPlanRecord, UUID(value.plan_id))
        if not record:
            self.session.add(
                ResearchSearchPlanRecord(
                    id=UUID(value.plan_id),
                    task_id=value.task_id,
                    criteria_snapshot_id=UUID(value.criteria_snapshot_id),
                    plan_json=value.model_dump(mode="json"),
                    created_at=value.created_at,
                )
            )
            await self.session.flush()
        return value

    async def save_run(self, value: ResearchRun) -> ResearchRun:
        record = await self.session.get(ResearchRunRecord, UUID(value.research_run_id))
        data = value.model_dump(mode="json")
        fields = {
            "task_id": value.task_id,
            "criteria_snapshot_id": UUID(value.criteria_snapshot_id),
            "search_plan_id": UUID(value.search_plan_id)
            if value.search_plan_id
            else None,
            "status": value.status.value,
            "stage": value.stage,
            "budget_json": data["budget"],
            "used_budget_json": value.used_budget,
            "raw_candidate_set_id": UUID(value.raw_candidate_set_id)
            if value.raw_candidate_set_id
            else None,
            "cheap_enriched_set_id": UUID(value.cheap_enriched_set_id)
            if value.cheap_enriched_set_id
            else None,
            "filtered_candidate_set_id": UUID(value.filtered_candidate_set_id)
            if value.filtered_candidate_set_id
            else None,
            "researched_candidate_set_id": UUID(value.researched_candidate_set_id)
            if value.researched_candidate_set_id
            else None,
            "error_code": value.error_code,
            "started_at": value.started_at,
            "finished_at": value.finished_at,
        }
        if record:
            for key, item in fields.items():
                setattr(record, key, item)
        else:
            self.session.add(
                ResearchRunRecord(id=UUID(value.research_run_id), **fields)
            )
        await self.session.flush()
        return value

    async def save_candidate(
        self, value: RawEnterpriseCandidate
    ) -> RawEnterpriseCandidate:
        payload = value.model_dump(mode="json")
        record = await self.session.get(
            EnterpriseCandidateRecord, UUID(value.candidate_id)
        )
        fields = {
            "research_run_id": UUID(value.research_run_id),
            "source_provider": value.source_provider,
            "source_entity_id": value.source_entity_id,
            "source_name": value.source_name,
            "normalized_name": value.normalized_name,
            "provisional_json": payload,
            "research_status": value.status.value,
            "created_at": value.discovered_at,
            "updated_at": value.discovered_at,
        }
        if record:
            for key, item in fields.items():
                setattr(record, key, item)
        else:
            self.session.add(
                EnterpriseCandidateRecord(id=UUID(value.candidate_id), **fields)
            )
        await self.session.flush()
        return value

    async def save_candidate_set(self, value: CandidateSet) -> CandidateSet:
        value = value.model_copy(update={"candidate_count": len(value.candidate_ids)})
        if not await self.session.get(CandidateSetRecord, UUID(value.candidate_set_id)):
            self.session.add(
                CandidateSetRecord(
                    id=UUID(value.candidate_set_id),
                    research_run_id=UUID(value.research_run_id),
                    parent_set_id=UUID(value.parent_set_id)
                    if value.parent_set_id
                    else None,
                    stage=value.stage,
                    criteria_snapshot_id=UUID(value.criteria_snapshot_id),
                    search_plan_id=UUID(value.search_plan_id),
                    candidate_count=value.candidate_count,
                    created_at=value.created_at,
                )
            )
            for position, candidate_id in enumerate(value.candidate_ids):
                self.session.add(
                    CandidateSetMemberRecord(
                        candidate_set_id=UUID(value.candidate_set_id),
                        candidate_id=UUID(candidate_id),
                        position=position,
                        selection_reason=value.stage,
                        created_at=value.created_at,
                    )
                )
            await self.session.flush()
        return value

    async def save_source(self, value: SourceRecord) -> SourceRecord:
        if not await self.session.get(
            ResearchSourceRecordModel, UUID(value.source_record_id)
        ):
            self.session.add(
                ResearchSourceRecordModel(
                    id=UUID(value.source_record_id),
                    research_run_id=UUID(value.research_run_id),
                    candidate_id=UUID(value.candidate_id),
                    provider=value.provider,
                    source_type=value.source_type.value,
                    source_id=value.source_id,
                    source_url=value.source_url,
                    retrieved_at=value.retrieved_at,
                    payload_json=value.payload_json,
                    content_text=value.content_text,
                    content_hash=value.content_hash,
                    http_status=value.http_status,
                )
            )
            await self.session.flush()
        return value

    async def save_tool_run(self, value: ToolRun) -> ToolRun:
        existing = await self.session.scalar(
            select(ToolRunRecord).where(
                ToolRunRecord.request_hash == value.request_hash
            )
        )
        if not existing:
            data = value.model_dump(mode="json")
            self.session.add(
                ToolRunRecord(
                    id=UUID(value.tool_run_id),
                    research_run_id=UUID(value.research_run_id),
                    task_id=value.task_id,
                    query_id=UUID(value.query_id) if value.query_id else None,
                    tool_name=value.tool_name,
                    provider=value.provider,
                    request_hash=value.request_hash,
                    request_summary=value.request_summary,
                    status=value.status.value,
                    latency_ms=value.latency_ms,
                    retry_count=value.retry_count,
                    error_code=value.error_code,
                    result_json=data.get("result"),
                    started_at=value.started_at,
                    finished_at=value.finished_at,
                )
            )
            await self.session.flush()
        return value

    async def save_batch(self, value: ResearchBatch) -> ResearchBatch:
        if not await self.session.get(ResearchBatchRecord, UUID(value.batch_id)):
            self.session.add(
                ResearchBatchRecord(
                    id=UUID(value.batch_id),
                    research_run_id=UUID(value.research_run_id),
                    stage=value.stage,
                    batch_index=value.batch_index,
                    status=value.status,
                    candidate_ids=value.candidate_ids,
                    query_ids=value.query_ids,
                    started_at=value.started_at,
                    finished_at=value.finished_at,
                    error_code=value.error_code,
                )
            )
            await self.session.flush()
        return value
