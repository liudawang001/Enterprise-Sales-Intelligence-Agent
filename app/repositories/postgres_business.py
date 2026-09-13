"""Synchronous PostgreSQL-backed repositories used by the production graph.

The graph services intentionally expose synchronous repository methods.  These
adapters preserve that contract while using a short transaction per operation,
and hydrate a process-local read cache from PostgreSQL on construction.  The
cache is an acceleration layer only; PostgreSQL is the durable source of truth.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.agent.enums import TaskStage, TaskStatus
from app.criteria.models import LeadCriteria
from app.delivery.models import DeliveryBundle
from app.domain.task import LeadTask
from app.entities.models import (
    CanonicalEnterprise,
    EnterpriseCandidateLink,
    EnterpriseLocation,
    EnterpriseRelation,
    EntityResolutionRun,
    ResolutionDecision,
)
from app.evidence.models import Evidence, ResolvedField, VerificationRun, VerifiedEnterpriseProfile
from app.execution.models import ArtifactValidity, TaskExecutionSnapshot
from app.exports.models import ExportJob, ExportStatus
from app.knowledge.models import KnowledgeChunk, KnowledgeDocument
from app.knowledge.repository import InMemoryKnowledgeRepository
from app.mutation.models import ReexecutionPlan, TaskMutation
from app.mutation.repository import InMemoryMutationRepository
from app.persistence.models.chunk import KnowledgeChunkRecord
from app.persistence.models.delivery import DeliverySnapshotRecord, ExportRecord
from app.persistence.models.document import KnowledgeDocumentRecord
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
from app.persistence.models.rule import (
    BusinessRuleRecord,
    LeadCriteriaSnapshotRecord,
    MarketingRuleRecord,
)
from app.persistence.models.task import (
    LeadTaskRecord,
    LeadTaskVersionRecord,
    TaskExecutionSnapshotRecord,
    TaskMutationRecord,
    TaskReexecutionPlanRecord,
)
from app.persistence.models.verification import (
    CanonicalEnterpriseRecord,
    EnterpriseCandidateLinkRecord,
    EnterpriseEvidenceRecord,
    EnterpriseLocationRecord,
    EnterpriseRelationRecord,
    EntityResolutionDecisionRecord,
    EntityResolutionRunRecord,
    LeadScoreRecord,
    RecommendationReasonRecord,
    ResolvedFieldRecord,
    ScoringProfileRecord,
    VerificationRunRecord,
    VerifiedEnterpriseProfileRecord,
    VerifiedLeadSetRecord,
)
from app.repositories.delivery_snapshot_repository import InMemoryDeliverySnapshotRepository
from app.repositories.enterprise_repository import InMemoryEnterpriseRepository
from app.repositories.evidence_repository import InMemoryEvidenceRepository
from app.repositories.export_repository import InMemoryExportRepository
from app.repositories.lead_score_repository import InMemoryLeadScoreRepository
from app.repositories.mock_task_repository import MockTaskRepository
from app.research.models import (
    CandidateSet,
    RawEnterpriseCandidate,
    ResearchBatch,
    ResearchRun,
    SearchPlan,
    SourceRecord,
    ToolResult,
    ToolRun,
)
from app.research.repository import InMemoryResearchRepository
from app.rules.models import BusinessRule, ConstraintType, RuleSourceType
from app.rules.service import InMemoryRuleRepository
from app.scoring.models import LeadScore, RecommendationReason, ScoringProfile, VerifiedLeadSet
from app.tasks.models import TaskVersion

SessionFactory = sessionmaker[Session]


def _uuid(value: str | UUID | None) -> UUID | None:
    return UUID(str(value)) if value else None


def _enum_value(value):
    return getattr(value, "value", value)


class _PostgresBacked:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def _transaction(self, operation: Callable[[Session], None]) -> None:
        with self.session_factory.begin() as session:
            operation(session)


class PostgresTaskRepository(MockTaskRepository, _PostgresBacked):
    def __init__(self, session_factory: SessionFactory) -> None:
        MockTaskRepository.__init__(self)
        _PostgresBacked.__init__(self, session_factory)
        self._load()

    def _load(self) -> None:
        with self.session_factory() as session:
            heads = list(session.scalars(select(LeadTaskRecord)).all())
            versions = list(
                session.scalars(
                    select(LeadTaskVersionRecord).order_by(LeadTaskVersionRecord.task_id, LeadTaskVersionRecord.version)
                ).all()
            )
        by_task: dict[UUID, list[TaskVersion]] = {}
        for row in versions:
            value = TaskVersion(
                version_id=str(row.id),
                task_id=str(row.task_id),
                version=row.version,
                parent_version=row.parent_version,
                business=row.business_code,
                region=row.region,
                target_count=row.target_count,
                constraints=row.constraints_json,
                required_fields=row.required_fields,
                export_fields=row.export_fields,
                source_message_id=row.source_message_id,
                mutation_id=str(row.mutation_id) if row.mutation_id else None,
                created_at=row.created_at,
            )
            by_task.setdefault(row.task_id, []).append(value)
        for row in heads:
            task_versions = by_task.get(row.id, [])
            current = next((item for item in task_versions if item.version == row.active_version), None)
            if current is None:
                continue
            task = LeadTask(
                task_id=str(row.id),
                session_id=row.thread_id,
                workspace_id=row.workspace_id,
                business=current.business,
                region=current.region,
                target_count=current.target_count,
                constraints=current.constraints,
                required_fields=current.required_fields,
                export_fields=current.export_fields,
                stage=TaskStage(row.stage),
                status=TaskStatus(row.status),
                version=row.active_version,
                source_message_id=current.source_message_id,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            self._tasks[task.task_id] = task
            self._versions[task.task_id] = task_versions
            if row.is_active:
                self._active_by_session[f"{row.workspace_id}:{row.thread_id}"] = task.task_id
            for version in task_versions:
                if version.source_message_id:
                    self._create_requests.setdefault(
                        (f"{row.workspace_id}:{row.thread_id}", version.source_message_id), task.task_id
                    )
                if version.mutation_id and version.source_message_id:
                    self._mutation_requests[(task.task_id, version.source_message_id)] = version.version

    def _persist_task(self, task: LeadTask) -> None:
        versions = self._versions.get(task.task_id, [])

        def persist(session: Session) -> None:
            session.merge(
                LeadTaskRecord(
                    id=UUID(task.task_id),
                    thread_id=task.session_id,
                    workspace_id=task.workspace_id,
                    business_code=task.business,
                    active_version=task.version,
                    stage=task.stage.value,
                    status=task.status.value,
                    is_active=self._active_by_session.get(f"{task.workspace_id}:{task.session_id}") == task.task_id,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                )
            )
            for value in versions:
                session.merge(
                    LeadTaskVersionRecord(
                        id=UUID(value.version_id),
                        task_id=UUID(value.task_id),
                        version=value.version,
                        parent_version=value.parent_version,
                        business_code=value.business,
                        region=value.region,
                        target_count=value.target_count,
                        constraints_json=value.constraints,
                        required_fields=value.required_fields,
                        export_fields=value.export_fields,
                        source_message_id=value.source_message_id,
                        mutation_id=_uuid(value.mutation_id),
                        created_at=value.created_at,
                    )
                )

        self._transaction(persist)

    def create_task(self, session_id: str, source_message_id: str | None = None) -> LeadTask:
        value = super().create_task(session_id, source_message_id)
        self._persist_task(value)
        return value

    def update_task(self, task: LeadTask, **kwargs) -> LeadTask:
        value = super().update_task(task, **kwargs)
        self._persist_task(value)
        return value

    def activate_task(self, session_id: str, task_id: str) -> LeadTask:
        value = super().activate_task(session_id, task_id)

        def persist(session: Session) -> None:
            session.execute(
                update(LeadTaskRecord)
                .where(
                    LeadTaskRecord.workspace_id == value.workspace_id,
                    LeadTaskRecord.thread_id == session_id,
                )
                .values(is_active=False)
            )
            session.execute(
                update(LeadTaskRecord)
                .where(LeadTaskRecord.id == UUID(task_id))
                .values(is_active=True, updated_at=value.updated_at)
            )

        self._transaction(persist)
        return value

    def restore_task(self, task: LeadTask, versions: list[TaskVersion] | None = None) -> LeadTask:
        value = super().restore_task(task, versions)
        self._persist_task(value)
        return value


class PostgresResearchRepository(InMemoryResearchRepository, _PostgresBacked):
    def __init__(self, session_factory: SessionFactory) -> None:
        InMemoryResearchRepository.__init__(self)
        _PostgresBacked.__init__(self, session_factory)
        self._load()

    def _load(self) -> None:
        with self.session_factory() as session:
            for row in session.scalars(select(ResearchSearchPlanRecord)):
                value = SearchPlan.model_validate(row.plan_json)
                self.plans[value.plan_id] = value
            for row in session.scalars(select(ResearchRunRecord)):
                value = ResearchRun(
                    research_run_id=str(row.id),
                    task_id=row.task_id,
                    criteria_snapshot_id=str(row.criteria_snapshot_id),
                    search_plan_id=str(row.search_plan_id) if row.search_plan_id else None,
                    status=row.status,
                    stage=row.stage,
                    budget=row.budget_json,
                    used_budget=row.used_budget_json,
                    raw_candidate_set_id=str(row.raw_candidate_set_id) if row.raw_candidate_set_id else None,
                    cheap_enriched_set_id=str(row.cheap_enriched_set_id) if row.cheap_enriched_set_id else None,
                    filtered_candidate_set_id=(
                        str(row.filtered_candidate_set_id) if row.filtered_candidate_set_id else None
                    ),
                    researched_candidate_set_id=str(row.researched_candidate_set_id)
                    if row.researched_candidate_set_id
                    else None,
                    error_code=row.error_code,
                    started_at=row.started_at,
                    finished_at=row.finished_at,
                )
                self.runs[value.research_run_id] = value
                self.events[value.research_run_id] = list(row.events_json or [])
            for row in session.scalars(select(EnterpriseCandidateRecord)):
                value = RawEnterpriseCandidate.model_validate(row.provisional_json)
                self.candidates[value.candidate_id] = value
            members: dict[UUID, list[tuple[int, str]]] = {}
            for row in session.scalars(select(CandidateSetMemberRecord)):
                members.setdefault(row.candidate_set_id, []).append((row.position, str(row.candidate_id)))
            for row in session.scalars(select(CandidateSetRecord)):
                candidate_ids = [item for _, item in sorted(members.get(row.id, []))]
                value = CandidateSet(
                    candidate_set_id=str(row.id),
                    research_run_id=str(row.research_run_id),
                    parent_set_id=str(row.parent_set_id) if row.parent_set_id else None,
                    stage=row.stage,
                    criteria_snapshot_id=str(row.criteria_snapshot_id),
                    search_plan_id=str(row.search_plan_id),
                    candidate_ids=candidate_ids,
                    candidate_count=row.candidate_count,
                    created_at=row.created_at,
                )
                self.candidate_sets[value.candidate_set_id] = value
            for row in session.scalars(select(ResearchSourceRecordModel)):
                value = SourceRecord(
                    source_record_id=str(row.id),
                    research_run_id=str(row.research_run_id),
                    candidate_id=str(row.candidate_id),
                    provider=row.provider,
                    source_type=row.source_type,
                    source_id=row.source_id,
                    source_url=row.source_url,
                    payload_json=row.payload_json,
                    content_text=row.content_text,
                    content_hash=row.content_hash,
                    http_status=row.http_status,
                    retrieved_at=row.retrieved_at,
                )
                self.sources[value.source_record_id] = value
            for row in session.scalars(select(ToolRunRecord)):
                value = ToolRun(
                    tool_run_id=str(row.id),
                    research_run_id=str(row.research_run_id),
                    task_id=row.task_id,
                    query_id=str(row.query_id) if row.query_id else None,
                    tool_name=row.tool_name,
                    provider=row.provider,
                    request_hash=row.request_hash,
                    request_summary=row.request_summary,
                    status=row.status,
                    latency_ms=row.latency_ms,
                    retry_count=row.retry_count,
                    trace_id=row.trace_id,
                    run_id=str(row.run_id) if row.run_id else None,
                    fence_token=row.fence_token,
                    cache_hit=row.cache_hit,
                    rate_limit_wait_ms=row.rate_limit_wait_ms,
                    provider_latency_ms=row.provider_latency_ms,
                    error_code=row.error_code,
                    result=ToolResult.model_validate(row.result_json) if row.result_json else None,
                    started_at=row.started_at,
                    finished_at=row.finished_at,
                )
                self.tool_runs[value.tool_run_id] = value
            for row in session.scalars(select(ResearchBatchRecord)):
                value = ResearchBatch(
                    batch_id=str(row.id),
                    research_run_id=str(row.research_run_id),
                    stage=row.stage,
                    batch_index=row.batch_index,
                    status=row.status,
                    candidate_ids=row.candidate_ids,
                    query_ids=row.query_ids,
                    error_code=row.error_code,
                    started_at=row.started_at,
                    finished_at=row.finished_at,
                )
                self.batches[value.batch_id] = value
                self.batch_results[value.batch_id] = list(value.candidate_ids)

    def save_plan(self, value: SearchPlan) -> SearchPlan:
        saved = super().save_plan(value)
        self._transaction(
            lambda session: session.merge(
                ResearchSearchPlanRecord(
                    id=UUID(saved.plan_id),
                    task_id=saved.task_id,
                    criteria_snapshot_id=UUID(saved.criteria_snapshot_id),
                    plan_json=saved.model_dump(mode="json"),
                    created_at=saved.created_at,
                )
            )
        )
        return saved

    def save_run(self, value: ResearchRun) -> ResearchRun:
        saved = super().save_run(value)
        self._transaction(lambda session: session.merge(self._run_record(saved)))
        return saved

    def _run_record(self, value: ResearchRun) -> ResearchRunRecord:
        return ResearchRunRecord(
            id=UUID(value.research_run_id),
            task_id=value.task_id,
            criteria_snapshot_id=UUID(value.criteria_snapshot_id),
            search_plan_id=_uuid(value.search_plan_id),
            status=_enum_value(value.status),
            stage=value.stage,
            budget_json=value.budget.model_dump(mode="json"),
            used_budget_json=value.used_budget,
            raw_candidate_set_id=_uuid(value.raw_candidate_set_id),
            cheap_enriched_set_id=_uuid(value.cheap_enriched_set_id),
            filtered_candidate_set_id=_uuid(value.filtered_candidate_set_id),
            researched_candidate_set_id=_uuid(value.researched_candidate_set_id),
            error_code=value.error_code,
            events_json=self.events.get(value.research_run_id, []),
            started_at=value.started_at,
            finished_at=value.finished_at,
        )

    def save_candidate(self, value: RawEnterpriseCandidate) -> RawEnterpriseCandidate:
        saved = super().save_candidate(value)
        self._transaction(
            lambda session: session.merge(
                EnterpriseCandidateRecord(
                    id=UUID(saved.candidate_id),
                    research_run_id=UUID(saved.research_run_id),
                    source_provider=saved.source_provider,
                    source_entity_id=saved.source_entity_id,
                    source_name=saved.source_name,
                    normalized_name=saved.normalized_name,
                    provisional_json=saved.model_dump(mode="json"),
                    research_status=_enum_value(saved.status),
                    created_at=saved.discovered_at,
                    updated_at=saved.discovered_at,
                )
            )
        )
        return saved

    def save_candidate_set(self, value: CandidateSet) -> CandidateSet:
        saved = super().save_candidate_set(value)

        def persist(session: Session) -> None:
            session.merge(
                CandidateSetRecord(
                    id=UUID(saved.candidate_set_id),
                    research_run_id=UUID(saved.research_run_id),
                    parent_set_id=_uuid(saved.parent_set_id),
                    stage=saved.stage,
                    criteria_snapshot_id=UUID(saved.criteria_snapshot_id),
                    search_plan_id=UUID(saved.search_plan_id),
                    candidate_count=saved.candidate_count,
                    created_at=saved.created_at,
                )
            )
            session.execute(
                delete(CandidateSetMemberRecord).where(
                    CandidateSetMemberRecord.candidate_set_id == UUID(saved.candidate_set_id)
                )
            )
            for position, candidate_id in enumerate(saved.candidate_ids):
                session.add(
                    CandidateSetMemberRecord(
                        candidate_set_id=UUID(saved.candidate_set_id),
                        candidate_id=UUID(candidate_id),
                        position=position,
                        selection_reason=saved.stage,
                        created_at=saved.created_at,
                    )
                )

        self._transaction(persist)
        return saved

    def save_source(self, value: SourceRecord) -> SourceRecord:
        saved = super().save_source(value)
        self._transaction(
            lambda session: session.merge(
                ResearchSourceRecordModel(
                    id=UUID(saved.source_record_id),
                    research_run_id=UUID(saved.research_run_id),
                    candidate_id=UUID(saved.candidate_id),
                    provider=saved.provider,
                    source_type=_enum_value(saved.source_type),
                    source_id=saved.source_id,
                    source_url=saved.source_url,
                    retrieved_at=saved.retrieved_at,
                    payload_json=saved.payload_json,
                    content_text=saved.content_text,
                    content_hash=saved.content_hash,
                    http_status=saved.http_status,
                )
            )
        )
        return saved

    def save_tool_run(self, value: ToolRun) -> ToolRun:
        saved = super().save_tool_run(value)
        payload = saved.model_dump(mode="json")

        def persist(session: Session) -> None:
            existing = session.scalar(select(ToolRunRecord.id).where(ToolRunRecord.request_hash == saved.request_hash))
            if existing:
                return
            session.add(
                ToolRunRecord(
                    id=UUID(saved.tool_run_id),
                    research_run_id=UUID(saved.research_run_id),
                    task_id=saved.task_id,
                    query_id=_uuid(saved.query_id),
                    tool_name=saved.tool_name,
                    provider=saved.provider,
                    request_hash=saved.request_hash,
                    request_summary=saved.request_summary,
                    status=_enum_value(saved.status),
                    latency_ms=saved.latency_ms,
                    retry_count=saved.retry_count,
                    trace_id=saved.trace_id,
                    run_id=_uuid(saved.run_id),
                    fence_token=saved.fence_token,
                    cache_hit=saved.cache_hit,
                    rate_limit_wait_ms=saved.rate_limit_wait_ms,
                    provider_latency_ms=saved.provider_latency_ms,
                    error_code=saved.error_code,
                    result_json=payload.get("result"),
                    started_at=saved.started_at,
                    finished_at=saved.finished_at,
                )
            )

        self._transaction(persist)
        return saved

    def save_batch_result(self, batch_id: str, candidate_ids: list[str], **kwargs) -> str:
        result = super().save_batch_result(batch_id, candidate_ids, **kwargs)
        value = self.batches[batch_id]
        self._transaction(
            lambda session: session.merge(
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
        )
        return result

    def record_event(self, research_run_id: str, event: str, **data: object) -> None:
        super().record_event(research_run_id, event, **data)
        if research_run_id in self.runs:
            self._transaction(lambda session: session.merge(self._run_record(self.runs[research_run_id])))


class PostgresEnterpriseRepository(InMemoryEnterpriseRepository, _PostgresBacked):
    def __init__(self, research_repository: PostgresResearchRepository, session_factory: SessionFactory) -> None:
        InMemoryEnterpriseRepository.__init__(self, research_repository)
        _PostgresBacked.__init__(self, session_factory)
        self._load()

    def _load(self) -> None:
        with self.session_factory() as session:
            for row in session.scalars(select(EntityResolutionRunRecord)):
                value = EntityResolutionRun(
                    resolution_run_id=str(row.id),
                    task_id=row.task_id,
                    researched_candidate_set_id=str(row.candidate_set_id),
                    status=row.status,
                    rule_version=row.rule_version,
                    candidate_count=row.candidate_count,
                    enterprise_count=row.enterprise_count,
                    started_at=row.started_at,
                    finished_at=row.finished_at,
                )
                self.resolution_runs[value.resolution_run_id] = value
            for row in session.scalars(select(CanonicalEnterpriseRecord)):
                value = CanonicalEnterprise(
                    enterprise_id=str(row.id),
                    canonical_name=row.canonical_name,
                    entity_type=row.entity_type,
                    parent_enterprise_id=str(row.parent_enterprise_id) if row.parent_enterprise_id else None,
                    unified_social_credit_code=row.unified_social_credit_code,
                    primary_region=row.primary_region,
                    primary_website=row.primary_website,
                    resolution_status=row.resolution_status,
                    resolution_confidence=row.resolution_confidence,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                self.enterprises[value.enterprise_id] = value
            for row in session.scalars(select(EnterpriseCandidateLinkRecord)):
                value = EnterpriseCandidateLink(
                    enterprise_id=str(row.enterprise_id),
                    candidate_id=str(row.candidate_id),
                    resolution_run_id=str(row.resolution_run_id),
                    decision=row.decision,
                    confidence=row.confidence,
                    created_at=row.created_at,
                )
                self.candidate_links[value.candidate_id] = value
            for row in session.scalars(select(EnterpriseRelationRecord)):
                value = EnterpriseRelation(
                    relation_id=str(row.id),
                    from_enterprise_id=str(row.from_enterprise_id),
                    to_enterprise_id=str(row.to_enterprise_id),
                    relation_type=row.relation_type,
                    confidence=row.confidence,
                    evidence_ids=row.evidence_ids,
                    created_at=row.created_at,
                )
                self.relations[value.relation_id] = value
            for row in session.scalars(select(EnterpriseLocationRecord)):
                value = EnterpriseLocation(
                    location_id=str(row.id),
                    enterprise_id=str(row.enterprise_id),
                    location_type=row.location_type,
                    address=row.address,
                    normalized_address=row.normalized_address,
                    lat=row.lat,
                    lng=row.lng,
                    evidence_ids=row.evidence_ids,
                    verification_status=row.verification_status,
                )
                self.locations[value.location_id] = value
            for row in session.scalars(select(EntityResolutionDecisionRecord)):
                value = ResolutionDecision.model_validate(row.audit_json)
                self.resolution_audits.setdefault(str(row.resolution_run_id), []).append(value)
        source_ids: dict[str, list[str]] = {}
        for link in self.candidate_links.values():
            source_ids.setdefault(link.enterprise_id, []).append(link.candidate_id)
        for enterprise_id, candidate_ids in source_ids.items():
            if enterprise_id in self.enterprises:
                self.enterprises[enterprise_id] = self.enterprises[enterprise_id].model_copy(
                    update={"source_candidate_ids": candidate_ids}
                )

    def save_resolution_run(self, value: EntityResolutionRun) -> EntityResolutionRun:
        saved = super().save_resolution_run(value)
        self._transaction(
            lambda session: session.merge(
                EntityResolutionRunRecord(
                    id=UUID(saved.resolution_run_id),
                    task_id=saved.task_id,
                    candidate_set_id=UUID(saved.researched_candidate_set_id),
                    status=saved.status,
                    rule_version=saved.rule_version,
                    candidate_count=saved.candidate_count,
                    enterprise_count=saved.enterprise_count,
                    started_at=saved.started_at,
                    finished_at=saved.finished_at,
                )
            )
        )
        return saved

    def save_enterprise(self, value: CanonicalEnterprise) -> CanonicalEnterprise:
        saved = super().save_enterprise(value)
        self._transaction(
            lambda session: session.merge(
                CanonicalEnterpriseRecord(
                    id=UUID(saved.enterprise_id),
                    canonical_name=saved.canonical_name,
                    entity_type=_enum_value(saved.entity_type),
                    parent_enterprise_id=_uuid(saved.parent_enterprise_id),
                    unified_social_credit_code=saved.unified_social_credit_code,
                    primary_region=saved.primary_region,
                    primary_website=saved.primary_website,
                    resolution_status=_enum_value(saved.resolution_status),
                    resolution_confidence=saved.resolution_confidence,
                    created_at=saved.created_at,
                    updated_at=saved.updated_at,
                )
            )
        )
        return saved

    def save_candidate_link(self, value: EnterpriseCandidateLink) -> EnterpriseCandidateLink:
        saved = super().save_candidate_link(value)
        self._transaction(
            lambda session: session.merge(
                EnterpriseCandidateLinkRecord(
                    enterprise_id=UUID(saved.enterprise_id),
                    candidate_id=UUID(saved.candidate_id),
                    resolution_run_id=UUID(saved.resolution_run_id),
                    decision=_enum_value(saved.decision),
                    confidence=saved.confidence,
                    created_at=saved.created_at,
                )
            )
        )
        return saved

    def save_location(self, value: EnterpriseLocation) -> EnterpriseLocation:
        saved = super().save_location(value)
        self._transaction(
            lambda session: session.merge(
                EnterpriseLocationRecord(
                    id=UUID(saved.location_id),
                    enterprise_id=UUID(saved.enterprise_id),
                    location_type=_enum_value(saved.location_type),
                    address=saved.address,
                    normalized_address=saved.normalized_address,
                    lat=saved.lat,
                    lng=saved.lng,
                    evidence_ids=saved.evidence_ids,
                    verification_status=saved.verification_status,
                )
            )
        )
        return saved

    def save_resolution_decision(self, run_id: str, value: ResolutionDecision) -> None:
        super().save_resolution_decision(run_id, value)
        self._transaction(
            lambda session: session.add(
                EntityResolutionDecisionRecord(
                    id=uuid4(),
                    resolution_run_id=UUID(run_id),
                    left_candidate_id=UUID(value.left_candidate_id),
                    right_candidate_id=UUID(value.right_candidate_id),
                    relation=_enum_value(value.relation),
                    confidence=value.confidence,
                    audit_json=value.model_dump(mode="json"),
                )
            )
        )

    def materialize_relations(
        self,
        decisions: list[ResolutionDecision],
        enterprise_by_candidate: dict[str, CanonicalEnterprise],
    ) -> None:
        before = set(self.relations)
        super().materialize_relations(decisions, enterprise_by_candidate)
        created = [value for key, value in self.relations.items() if key not in before]

        def persist(session: Session) -> None:
            for value in created:
                session.merge(
                    EnterpriseRelationRecord(
                        id=UUID(value.relation_id),
                        from_enterprise_id=UUID(value.from_enterprise_id),
                        to_enterprise_id=UUID(value.to_enterprise_id),
                        relation_type=_enum_value(value.relation_type),
                        confidence=value.confidence,
                        evidence_ids=value.evidence_ids,
                        created_at=value.created_at,
                    )
                )

        if created:
            self._transaction(persist)


class PostgresEvidenceRepository(InMemoryEvidenceRepository, _PostgresBacked):
    def __init__(self, session_factory: SessionFactory) -> None:
        InMemoryEvidenceRepository.__init__(self)
        _PostgresBacked.__init__(self, session_factory)
        self._load()

    def _load(self) -> None:
        with self.session_factory() as session:
            for row in session.scalars(select(VerificationRunRecord)):
                value = VerificationRun(
                    verification_run_id=str(row.id),
                    task_id=row.task_id,
                    researched_candidate_set_id=str(row.candidate_set_id),
                    resolution_run_id=str(row.resolution_run_id),
                    status=row.status,
                    budget=row.budget_json,
                    used_budget=row.used_budget_json,
                    warnings=row.warnings,
                    started_at=row.started_at,
                    finished_at=row.finished_at,
                )
                self.runs[value.verification_run_id] = value
            for row in session.scalars(select(EnterpriseEvidenceRecord)):
                value = Evidence(
                    evidence_id=str(row.id),
                    enterprise_id=str(row.enterprise_id),
                    field_name=row.field_name,
                    value=row.value_json,
                    normalized_value=row.normalized_value_json,
                    provider=row.provider,
                    source_type=row.source_type,
                    source_record_id=str(row.source_record_id),
                    source_url=row.source_url,
                    retrieved_at=row.retrieved_at,
                    confidence=row.confidence,
                    extraction_method=row.extraction_method,
                    raw_reference=row.raw_reference,
                    stale=row.stale,
                    created_at=row.created_at,
                )
                self.evidence[value.evidence_id] = value
            for row in session.scalars(select(ResolvedFieldRecord).order_by(ResolvedFieldRecord.resolved_at)):
                value = ResolvedField(
                    resolved_field_id=str(row.id),
                    enterprise_id=str(row.enterprise_id),
                    field_name=row.field_name,
                    primary_value=row.primary_value_json,
                    status=row.status,
                    confidence=row.confidence,
                    supporting_evidence_ids=row.supporting_evidence_ids,
                    conflicting_evidence_ids=row.conflicting_evidence_ids,
                    alternatives=row.alternatives,
                    selection_reason=row.selection_reason,
                    resolved_at=row.resolved_at,
                )
                self.resolved_fields[(value.enterprise_id, value.field_name)] = value
            profile_query = select(VerifiedEnterpriseProfileRecord).order_by(VerifiedEnterpriseProfileRecord.updated_at)
            for row in session.scalars(profile_query):
                value = VerifiedEnterpriseProfile.model_validate(row.profile_json)
                self.profiles[value.profile_id] = value
        profiles_by_run: dict[str, list[str]] = {}
        for value in self.profiles.values():
            profiles_by_run.setdefault(value.verification_run_id, []).append(value.profile_id)
        for run_id, profile_ids in profiles_by_run.items():
            if run_id in self.runs:
                self.runs[run_id] = self.runs[run_id].model_copy(update={"profile_ids": profile_ids})

    def save_run(self, value: VerificationRun) -> VerificationRun:
        saved = super().save_run(value)
        self._transaction(
            lambda session: session.merge(
                VerificationRunRecord(
                    id=UUID(saved.verification_run_id),
                    task_id=saved.task_id,
                    candidate_set_id=UUID(saved.researched_candidate_set_id),
                    resolution_run_id=UUID(saved.resolution_run_id),
                    status=saved.status,
                    budget_json=saved.budget.model_dump(mode="json"),
                    used_budget_json=saved.used_budget,
                    warnings=saved.warnings,
                    started_at=saved.started_at,
                    finished_at=saved.finished_at,
                )
            )
        )
        return saved

    def save_evidence(self, value: Evidence) -> Evidence:
        saved = super().save_evidence(value)
        self._transaction(
            lambda session: session.merge(
                EnterpriseEvidenceRecord(
                    id=UUID(saved.evidence_id),
                    enterprise_id=UUID(saved.enterprise_id),
                    field_name=saved.field_name,
                    value_json=saved.value,
                    normalized_value_json=saved.normalized_value,
                    provider=saved.provider,
                    source_type=_enum_value(saved.source_type),
                    source_record_id=UUID(saved.source_record_id),
                    source_url=saved.source_url,
                    retrieved_at=saved.retrieved_at,
                    confidence=saved.confidence,
                    extraction_method=saved.extraction_method,
                    raw_reference=saved.raw_reference,
                    stale=saved.stale,
                    created_at=saved.created_at,
                )
            )
        )
        return saved

    def save_resolved_field(self, value: ResolvedField, *, verification_run_id: str | None = None) -> ResolvedField:
        run_id = verification_run_id
        if run_id is None and self.runs:
            run_id = max(self.runs.values(), key=lambda item: item.started_at).verification_run_id
        if run_id is None:
            raise ValueError("VERIFICATION_RUN_REQUIRED")

        # The graph may resolve the same field more than once during a single
        # verification run.  Preserve the database identity selected by the
        # domain unique key instead of attempting to insert a second UUID.
        with self.session_factory.begin() as session:
            record = session.scalar(
                select(ResolvedFieldRecord).where(
                    ResolvedFieldRecord.verification_run_id == UUID(run_id),
                    ResolvedFieldRecord.enterprise_id == UUID(value.enterprise_id),
                    ResolvedFieldRecord.field_name == value.field_name,
                )
            )
            saved = value.model_copy(update={"resolved_field_id": str(record.id)} if record is not None else {})
            fields = {
                "primary_value_json": saved.primary_value,
                "status": _enum_value(saved.status),
                "confidence": saved.confidence,
                "supporting_evidence_ids": saved.supporting_evidence_ids,
                "conflicting_evidence_ids": saved.conflicting_evidence_ids,
                "alternatives": saved.alternatives,
                "selection_reason": saved.selection_reason,
                "resolved_at": saved.resolved_at,
            }
            if record is None:
                session.add(
                    ResolvedFieldRecord(
                        id=UUID(saved.resolved_field_id),
                        verification_run_id=UUID(run_id),
                        enterprise_id=UUID(saved.enterprise_id),
                        field_name=saved.field_name,
                        **fields,
                    )
                )
            else:
                for key, item in fields.items():
                    setattr(record, key, item)

        saved = InMemoryEvidenceRepository.save_resolved_field(self, saved)
        return saved

    def save_profile(self, value: VerifiedEnterpriseProfile) -> VerifiedEnterpriseProfile:
        saved = super().save_profile(value)
        self._transaction(
            lambda session: session.merge(
                VerifiedEnterpriseProfileRecord(
                    id=UUID(saved.profile_id),
                    verification_run_id=UUID(saved.verification_run_id),
                    enterprise_id=UUID(saved.enterprise_id),
                    profile_json=saved.model_dump(mode="json"),
                    status=_enum_value(saved.status),
                    evidence_coverage=saved.evidence_coverage,
                    updated_at=saved.updated_at,
                )
            )
        )
        return saved


class PostgresLeadScoreRepository(InMemoryLeadScoreRepository, _PostgresBacked):
    def __init__(self, session_factory: SessionFactory) -> None:
        InMemoryLeadScoreRepository.__init__(self)
        _PostgresBacked.__init__(self, session_factory)
        self._load()

    def _load(self) -> None:
        with self.session_factory() as session:
            for row in session.scalars(select(ScoringProfileRecord)):
                value = ScoringProfile.model_validate(row.profile_json)
                self.profiles[value.profile_id] = value
            for row in session.scalars(select(LeadScoreRecord).order_by(LeadScoreRecord.created_at)):
                value = LeadScore(
                    lead_score_id=str(row.id),
                    task_id=row.task_id,
                    task_version=row.task_version or 1,
                    enterprise_id=str(row.enterprise_id),
                    criteria_snapshot_id=str(row.criteria_snapshot_id),
                    scoring_profile_id=str(row.scoring_profile_id),
                    scoring_profile_version=row.scoring_profile_version,
                    total_score=row.total_score,
                    rank_status=row.rank_status,
                    verification_status=row.verification_status,
                    evidence_coverage=row.evidence_coverage,
                    component_scores=row.component_scores,
                    created_at=row.created_at,
                )
                self.scores[value.lead_score_id] = value
            scores = dict(self.scores)
            for row in session.scalars(select(RecommendationReasonRecord)):
                score = scores.get(str(row.lead_score_id))
                if score is None:
                    continue
                value = RecommendationReason(
                    enterprise_id=score.enterprise_id,
                    summary=row.summary,
                    reason_codes=row.reason_codes,
                    evidence_ids=row.evidence_ids,
                    generated_at=row.generated_at,
                )
                self.reasons[value.enterprise_id] = value
                self.reasons_by_score[str(row.lead_score_id)] = value
            for row in session.scalars(select(VerifiedLeadSetRecord).order_by(VerifiedLeadSetRecord.created_at)):
                value = VerifiedLeadSet(
                    lead_set_id=str(row.id),
                    task_id=row.task_id,
                    task_version=row.task_version or 1,
                    criteria_snapshot_id=str(row.criteria_snapshot_id),
                    scoring_profile_id=str(row.scoring_profile_id),
                    lead_ids=row.lead_ids,
                    lead_count=row.lead_count,
                    created_at=row.created_at,
                )
                self.lead_sets[value.lead_set_id] = value

    def save_profile(self, value: ScoringProfile) -> ScoringProfile:
        saved = super().save_profile(value)
        self._transaction(
            lambda session: session.merge(
                ScoringProfileRecord(
                    id=UUID(saved.profile_id),
                    business_code=saved.business_code,
                    version=saved.version,
                    profile_json=saved.model_dump(mode="json"),
                    active=saved.active,
                    created_at=saved.created_at,
                )
            )
        )
        return saved

    def save_score(self, value: LeadScore) -> LeadScore:
        saved = super().save_score(value)
        self._transaction(
            lambda session: session.merge(
                LeadScoreRecord(
                    id=UUID(saved.lead_score_id),
                    task_id=saved.task_id,
                    task_version=saved.task_version,
                    enterprise_id=UUID(saved.enterprise_id),
                    criteria_snapshot_id=UUID(saved.criteria_snapshot_id),
                    scoring_profile_id=UUID(saved.scoring_profile_id),
                    scoring_profile_version=saved.scoring_profile_version,
                    total_score=saved.total_score,
                    rank_status=_enum_value(saved.rank_status),
                    verification_status=saved.verification_status,
                    evidence_coverage=saved.evidence_coverage,
                    component_scores=[item.model_dump(mode="json") for item in saved.component_scores],
                    created_at=saved.created_at,
                )
            )
        )
        return saved

    def save_reason(self, value: RecommendationReason, *, lead_score_id: str | None = None) -> RecommendationReason:
        saved = super().save_reason(value, lead_score_id=lead_score_id)
        if not lead_score_id:
            raise ValueError("LEAD_SCORE_ID_REQUIRED")

        def persist(session: Session) -> None:
            row = session.scalar(
                select(RecommendationReasonRecord).where(
                    RecommendationReasonRecord.lead_score_id == UUID(lead_score_id)
                )
            )
            if row is None:
                row = RecommendationReasonRecord(id=uuid4(), lead_score_id=UUID(lead_score_id))
            row.summary = saved.summary
            row.reason_codes = saved.reason_codes
            row.evidence_ids = saved.evidence_ids
            row.generated_at = saved.generated_at
            session.add(row)

        self._transaction(persist)
        return saved

    def save_lead_set(self, value: VerifiedLeadSet) -> VerifiedLeadSet:
        saved = super().save_lead_set(value)
        self._transaction(
            lambda session: session.merge(
                VerifiedLeadSetRecord(
                    id=UUID(saved.lead_set_id),
                    task_id=saved.task_id,
                    task_version=saved.task_version,
                    criteria_snapshot_id=UUID(saved.criteria_snapshot_id),
                    scoring_profile_id=UUID(saved.scoring_profile_id),
                    lead_ids=saved.lead_ids,
                    lead_count=saved.lead_count,
                    created_at=saved.created_at,
                )
            )
        )
        return saved


class PostgresRuleRepository(InMemoryRuleRepository, _PostgresBacked):
    def __init__(self, session_factory: SessionFactory) -> None:
        InMemoryRuleRepository.__init__(self)
        _PostgresBacked.__init__(self, session_factory)
        self._load()

    @staticmethod
    def _business_rule(row: BusinessRuleRecord) -> BusinessRule:
        return BusinessRule(
            rule_id=str(row.id),
            business_code=row.business_code,
            field=row.field,
            operator=row.operator,
            value=row.value,
            value_type=row.value_type,
            source_type=row.source_type,
            constraint_type=row.constraint_type,
            modality=row.modality,
            weight=float(row.weight) if row.weight is not None else None,
            confidence=float(row.confidence),
            rationale=row.rationale,
            region=row.region,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
            status=row.status,
            source_key=row.source_key,
            created_at=row.created_at,
        )

    @staticmethod
    def _marketing_rule(row: MarketingRuleRecord) -> BusinessRule:
        return BusinessRule(
            rule_id=str(row.id),
            business_code=row.business_code,
            field=row.field,
            operator=row.operator,
            value=row.value,
            value_type=row.value_type,
            source_type=RuleSourceType.MARKETING_RULE,
            constraint_type=ConstraintType(row.constraint_type),
            weight=float(row.weight) if row.weight is not None else None,
            confidence=1.0,
            rationale=row.rationale,
            region=row.region,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
            status=row.status,
            source_key=row.source_key,
            created_at=row.created_at,
        )

    def _load(self) -> None:
        with self.session_factory() as session:
            for row in session.scalars(select(BusinessRuleRecord)):
                value = self._business_rule(row)
                self.rules[value.rule_id] = value
            for row in session.scalars(select(MarketingRuleRecord)):
                value = self._marketing_rule(row)
                self.marketing_rules[value.rule_id] = value
                self.rules.setdefault(value.rule_id, value)
            for row in session.scalars(select(LeadCriteriaSnapshotRecord)):
                value = LeadCriteria(
                    criteria_id=str(row.id),
                    task_id=row.task_id,
                    task_version=row.task_version,
                    business_code=row.business_code,
                    region_scope=row.region_scope,
                    target_count=row.target_count,
                    hard_constraints=row.hard_constraints,
                    soft_constraints=row.soft_constraints,
                    required_fields=row.required_fields,
                    ranking_preferences=row.ranking_preferences,
                    source_rule_ids=row.source_rule_ids,
                    warnings=row.warnings,
                    criteria_hash=row.criteria_hash,
                    created_at=row.created_at,
                )
                self.criteria[value.criteria_id] = value

    def upsert(self, rule: BusinessRule) -> BusinessRule:
        saved = super().upsert(rule)
        self._transaction(
            lambda session: session.merge(
                BusinessRuleRecord(
                    id=UUID(saved.rule_id),
                    business_code=saved.business_code,
                    field=saved.field,
                    operator=_enum_value(saved.operator),
                    value=saved.value,
                    value_type=saved.value_type,
                    source_type=_enum_value(saved.source_type),
                    constraint_type=_enum_value(saved.constraint_type),
                    modality=_enum_value(saved.modality) if saved.modality else None,
                    weight=saved.weight,
                    confidence=saved.confidence,
                    rationale=saved.rationale,
                    region=saved.region,
                    effective_from=saved.effective_from,
                    effective_to=saved.effective_to,
                    status=_enum_value(saved.status),
                    source_key=saved.source_key or saved.rule_id,
                    created_at=saved.created_at,
                    updated_at=saved.created_at,
                )
            )
        )
        return saved

    def save_marketing(self, rule: BusinessRule) -> BusinessRule:
        saved = super().save_marketing(rule)
        self._transaction(
            lambda session: session.merge(
                MarketingRuleRecord(
                    id=UUID(saved.rule_id),
                    business_code=saved.business_code,
                    field=saved.field,
                    operator=_enum_value(saved.operator),
                    value=saved.value,
                    value_type=saved.value_type,
                    constraint_type=_enum_value(saved.constraint_type),
                    weight=saved.weight,
                    region=saved.region,
                    effective_from=saved.effective_from,
                    effective_to=saved.effective_to,
                    rationale=saved.rationale,
                    status=_enum_value(saved.status),
                    source_key=saved.source_key or saved.rule_id,
                    created_at=saved.created_at,
                    updated_at=saved.created_at,
                )
            )
        )
        return saved

    def save_criteria(self, criteria: LeadCriteria) -> LeadCriteria:
        saved = super().save_criteria(criteria)
        payload = saved.model_dump(mode="json")
        self._transaction(
            lambda session: session.merge(
                LeadCriteriaSnapshotRecord(
                    id=UUID(saved.criteria_id),
                    task_id=saved.task_id,
                    task_version=saved.task_version,
                    business_code=saved.business_code,
                    region_scope=payload["region_scope"],
                    target_count=saved.target_count,
                    hard_constraints=payload["hard_constraints"],
                    soft_constraints=payload["soft_constraints"],
                    required_fields=payload["required_fields"],
                    ranking_preferences=payload["ranking_preferences"],
                    source_rule_ids=payload["source_rule_ids"],
                    warnings=payload["warnings"],
                    criteria_hash=saved.criteria_hash or "",
                    created_at=saved.created_at,
                )
            )
        )
        return saved


class PostgresMutationRepository(InMemoryMutationRepository, _PostgresBacked):
    def __init__(self, session_factory: SessionFactory) -> None:
        InMemoryMutationRepository.__init__(self)
        _PostgresBacked.__init__(self, session_factory)
        self._load()

    def _load(self) -> None:
        with self.session_factory() as session:
            for row in session.scalars(select(TaskMutationRecord).order_by(TaskMutationRecord.created_at)):
                value = TaskMutation(
                    mutation_id=str(row.id),
                    task_id=str(row.task_id),
                    source_message_id=row.source_message_id,
                    base_version=row.base_version,
                    target_version=row.target_version,
                    patch=row.patch_json,
                    preview=row.preview_json,
                    task_diff=row.task_diff_json,
                    criteria_diff=row.criteria_diff_json,
                    scope=row.scope,
                    reexecution_plan_id=str(row.reexecution_plan_id) if row.reexecution_plan_id else None,
                    created_at=row.created_at,
                )
                self.mutations[value.mutation_id] = value
                self._by_request[(value.task_id, value.source_message_id)] = value.mutation_id
            plan_query = select(TaskReexecutionPlanRecord).order_by(TaskReexecutionPlanRecord.created_at)
            for row in session.scalars(plan_query):
                value = ReexecutionPlan(
                    plan_id=str(row.id),
                    task_id=str(row.task_id),
                    base_version=row.base_version,
                    next_version=row.target_version,
                    original_scope=row.original_scope,
                    final_scope=row.final_scope,
                    start_stage=row.start_stage,
                    steps=row.steps_json,
                    reused_artifact_ids=row.reused_artifact_ids,
                    invalidated_artifact_ids=row.invalidated_artifact_ids,
                    required_fields=row.required_fields,
                    reason_codes=row.reason_codes,
                    reuse_decisions=row.reuse_decisions,
                    status=row.status,
                    escalation_reason=row.escalation_reason,
                    estimated_external_calls=row.estimated_external_calls,
                    created_at=row.created_at,
                    started_at=row.started_at,
                    finished_at=row.finished_at,
                )
                self.plans[value.plan_id] = value

    @staticmethod
    def _mutation_record(value: TaskMutation) -> TaskMutationRecord:
        return TaskMutationRecord(
            id=UUID(value.mutation_id),
            task_id=UUID(value.task_id),
            base_version=value.base_version,
            target_version=value.target_version,
            source_message_id=value.source_message_id,
            patch_json=value.patch.model_dump(mode="json"),
            preview_json=value.preview.model_dump(mode="json") if value.preview else None,
            task_diff_json=value.task_diff.model_dump(mode="json") if value.task_diff else None,
            criteria_diff_json=value.criteria_diff.model_dump(mode="json") if value.criteria_diff else None,
            scope=_enum_value(value.scope) if value.scope else None,
            reexecution_plan_id=_uuid(value.reexecution_plan_id),
            created_at=value.created_at,
        )

    @staticmethod
    def _plan_record(value: ReexecutionPlan) -> TaskReexecutionPlanRecord:
        return TaskReexecutionPlanRecord(
            id=UUID(value.plan_id),
            task_id=UUID(value.task_id),
            base_version=value.base_version,
            target_version=value.next_version,
            original_scope=_enum_value(value.original_scope),
            final_scope=_enum_value(value.final_scope),
            start_stage=value.start_stage,
            steps_json=value.steps,
            reused_artifact_ids=value.reused_artifact_ids,
            invalidated_artifact_ids=value.invalidated_artifact_ids,
            required_fields=value.required_fields,
            reason_codes=value.reason_codes,
            reuse_decisions={key: _enum_value(item) for key, item in value.reuse_decisions.items()},
            status=_enum_value(value.status),
            escalation_reason=value.escalation_reason,
            estimated_external_calls=value.estimated_external_calls,
            created_at=value.created_at,
            started_at=value.started_at,
            finished_at=value.finished_at,
        )

    def save_mutation(self, value: TaskMutation) -> TaskMutation:
        saved = super().save_mutation(value)
        self._transaction(lambda session: session.merge(self._mutation_record(saved)))
        return saved

    def update_mutation(self, value: TaskMutation) -> TaskMutation:
        saved = super().update_mutation(value)
        self._transaction(lambda session: session.merge(self._mutation_record(saved)))
        return saved

    def save_plan(self, value: ReexecutionPlan) -> ReexecutionPlan:
        saved = super().save_plan(value)
        self._transaction(lambda session: session.merge(self._plan_record(saved)))
        return saved


class PostgresExecutionSnapshotRepository(_PostgresBacked):
    def __init__(self, session_factory: SessionFactory) -> None:
        super().__init__(session_factory)
        self.snapshots: dict[str, TaskExecutionSnapshot] = {}
        self._current: dict[str, str] = {}
        with self.session_factory() as session:
            for row in session.scalars(
                select(TaskExecutionSnapshotRecord).order_by(TaskExecutionSnapshotRecord.created_at)
            ):
                value = self._from_record(row)
                self.snapshots[value.snapshot_id] = value
                if value.is_current:
                    self._current[value.task_id] = value.snapshot_id

    @staticmethod
    def _from_record(row: TaskExecutionSnapshotRecord) -> TaskExecutionSnapshot:
        return TaskExecutionSnapshot(
            snapshot_id=str(row.id),
            task_id=str(row.task_id),
            task_version=row.task_version,
            criteria_snapshot_id=str(row.criteria_snapshot_id) if row.criteria_snapshot_id else None,
            search_plan_id=str(row.search_plan_id) if row.search_plan_id else None,
            raw_candidate_set_id=str(row.raw_candidate_set_id) if row.raw_candidate_set_id else None,
            filtered_candidate_set_id=str(row.filtered_candidate_set_id) if row.filtered_candidate_set_id else None,
            researched_candidate_set_id=str(row.researched_candidate_set_id)
            if row.researched_candidate_set_id
            else None,
            verified_lead_set_id=str(row.verified_lead_set_id) if row.verified_lead_set_id else None,
            scoring_profile_id=str(row.scoring_profile_id) if row.scoring_profile_id else None,
            lead_score_set_id=str(row.lead_score_set_id) if row.lead_score_set_id else None,
            is_current=row.is_current,
            validity=row.validity,
            created_at=row.created_at,
        )

    @staticmethod
    def _record(value: TaskExecutionSnapshot) -> TaskExecutionSnapshotRecord:
        return TaskExecutionSnapshotRecord(
            id=UUID(value.snapshot_id),
            task_id=UUID(value.task_id),
            task_version=value.task_version,
            criteria_snapshot_id=_uuid(value.criteria_snapshot_id),
            search_plan_id=_uuid(value.search_plan_id),
            raw_candidate_set_id=_uuid(value.raw_candidate_set_id),
            filtered_candidate_set_id=_uuid(value.filtered_candidate_set_id),
            researched_candidate_set_id=_uuid(value.researched_candidate_set_id),
            verified_lead_set_id=_uuid(value.verified_lead_set_id),
            scoring_profile_id=_uuid(value.scoring_profile_id),
            lead_score_set_id=_uuid(value.lead_score_set_id),
            is_current=value.is_current,
            validity=_enum_value(value.validity),
            created_at=value.created_at,
        )

    def save(self, value: TaskExecutionSnapshot) -> TaskExecutionSnapshot:
        self.snapshots[value.snapshot_id] = deepcopy(value)
        self._transaction(lambda session: session.merge(self._record(value)))
        return deepcopy(value)

    def get(self, snapshot_id: str | None) -> TaskExecutionSnapshot | None:
        value = self.snapshots.get(snapshot_id or "")
        return deepcopy(value) if value else None

    def current(self, task_id: str) -> TaskExecutionSnapshot | None:
        return self.get(self._current.get(task_id))

    def for_version(self, task_id: str, version: int) -> TaskExecutionSnapshot | None:
        values = [
            value for value in self.snapshots.values() if value.task_id == task_id and value.task_version == version
        ]
        return deepcopy(values[-1]) if values else None

    def list_for_task(self, task_id: str) -> list[TaskExecutionSnapshot]:
        return [deepcopy(value) for value in self.snapshots.values() if value.task_id == task_id]

    def promote(self, value: TaskExecutionSnapshot, *, current_task_version: int) -> bool:
        if value.task_version != current_task_version:
            self.save(value.model_copy(update={"is_current": False, "validity": ArtifactValidity.SUPERSEDED}))
            return False
        previous = self.current(value.task_id)
        if previous:
            self.save(previous.model_copy(update={"is_current": False, "validity": ArtifactValidity.REUSABLE}))
        promoted = value.model_copy(update={"is_current": True, "validity": ArtifactValidity.CURRENT})
        self.save(promoted)
        self._current[value.task_id] = value.snapshot_id
        return True


class PostgresDeliverySnapshotRepository(InMemoryDeliverySnapshotRepository, _PostgresBacked):
    def __init__(self, session_factory: SessionFactory) -> None:
        InMemoryDeliverySnapshotRepository.__init__(self)
        _PostgresBacked.__init__(self, session_factory)
        with self.session_factory() as session:
            for row in session.scalars(select(DeliverySnapshotRecord)):
                if not row.bundle_json:
                    continue
                value = DeliveryBundle.model_validate(row.bundle_json)
                self.bundles[value.snapshot.snapshot_id] = value
                self._by_execution[
                    (value.snapshot.task_id, value.snapshot.task_version, value.snapshot.execution_snapshot_id)
                ] = value.snapshot.snapshot_id

    def save(self, value: DeliveryBundle) -> DeliveryBundle:
        saved = super().save(value)
        snapshot = saved.snapshot
        self._transaction(
            lambda session: session.merge(
                DeliverySnapshotRecord(
                    id=UUID(snapshot.snapshot_id),
                    task_id=snapshot.task_id,
                    task_version=snapshot.task_version,
                    criteria_snapshot_id=_uuid(snapshot.criteria_snapshot_id),
                    verified_lead_set_id=UUID(snapshot.verified_lead_set_id),
                    lead_score_set_id=UUID(snapshot.lead_score_set_id),
                    scoring_profile_id=_uuid(snapshot.scoring_profile_id),
                    execution_snapshot_id=_uuid(snapshot.execution_snapshot_id),
                    result_count=snapshot.result_count,
                    bundle_json=saved.model_dump(mode="json"),
                    created_at=snapshot.created_at,
                )
            )
        )
        return saved


class PostgresExportRepository(InMemoryExportRepository, _PostgresBacked):
    def __init__(self, session_factory: SessionFactory) -> None:
        InMemoryExportRepository.__init__(self)
        _PostgresBacked.__init__(self, session_factory)
        with self.session_factory() as session:
            for row in session.scalars(select(ExportRecord).order_by(ExportRecord.created_at)):
                value = self._from_record(row)
                self.jobs[value.export_id] = value
                self.events[value.export_id] = list(row.events_json or [])
                if value.status == ExportStatus.COMPLETED:
                    self._successful_by_hash[value.request_hash] = value.export_id

    @staticmethod
    def _from_record(row: ExportRecord) -> ExportJob:
        return ExportJob(
            export_id=str(row.id),
            snapshot_id=str(row.snapshot_id),
            task_id=row.task_id,
            workspace_id=row.workspace_id,
            task_version=row.task_version,
            status=row.status,
            format=row.format,
            requested_fields=row.fields_json,
            row_count=row.row_count,
            artifact_path=row.artifact_path,
            file_name=row.file_name,
            file_size=row.file_size,
            sha256=row.sha256,
            request_hash=row.request_hash,
            created_at=row.created_at,
            completed_at=row.completed_at,
            error_code=row.error_code,
            error_message=row.error_message,
        )

    def _record(self, value: ExportJob) -> ExportRecord:
        return ExportRecord(
            id=UUID(value.export_id),
            snapshot_id=UUID(value.snapshot_id),
            task_id=value.task_id,
            workspace_id=value.workspace_id,
            task_version=value.task_version,
            format=value.format,
            fields_json=value.requested_fields,
            status=_enum_value(value.status),
            row_count=value.row_count,
            artifact_path=value.artifact_path,
            file_name=value.file_name,
            file_size=value.file_size,
            sha256=value.sha256,
            request_hash=value.request_hash,
            created_at=value.created_at,
            completed_at=value.completed_at,
            error_code=value.error_code,
            error_message=value.error_message,
            events_json=self.events.get(value.export_id, []),
        )

    def save(self, value: ExportJob) -> ExportJob:
        saved = super().save(value)
        self._transaction(lambda session: session.merge(self._record(saved)))
        return saved

    def record_event(self, export_id: str, event: str, **data: object) -> None:
        super().record_event(export_id, event, **data)
        value = self.jobs.get(export_id)
        if value:
            self._transaction(lambda session: session.merge(self._record(value)))


class PostgresKnowledgeRepository(InMemoryKnowledgeRepository, _PostgresBacked):
    def __init__(self, session_factory: SessionFactory) -> None:
        InMemoryKnowledgeRepository.__init__(self)
        _PostgresBacked.__init__(self, session_factory)
        with self.session_factory() as session:
            for row in session.scalars(select(KnowledgeDocumentRecord)):
                value = KnowledgeDocument(
                    id=row.id,
                    title=row.title,
                    original_filename=row.original_filename,
                    file_hash=row.file_hash,
                    business=row.business,
                    document_type=row.document_type,
                    region=row.region,
                    access_scope=row.access_scope,
                    workspace_id=row.workspace_id,
                    authority=row.authority,
                    version=row.version,
                    effective_from=row.effective_from,
                    effective_to=row.effective_to,
                    status=row.status,
                    file_path=row.file_path,
                    page_count=row.page_count,
                    chunk_count=row.chunk_count,
                    error_message=row.error_message,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                self.documents[value.id] = value
            for row in session.scalars(select(KnowledgeChunkRecord)):
                value = KnowledgeChunk(
                    id=row.id,
                    document_id=row.document_id,
                    chunk_index=row.chunk_index,
                    content=row.content,
                    lexical_content=row.lexical_content,
                    embedding=list(row.embedding) if row.embedding is not None else None,
                    chunk_type=row.chunk_type,
                    page_start=row.page_start,
                    page_end=row.page_end,
                    section_path=row.section_path,
                    content_hash=row.content_hash,
                    metadata=row.metadata_json,
                )
                self.chunks[value.id] = value

    @staticmethod
    def _document_record(value: KnowledgeDocument) -> KnowledgeDocumentRecord:
        return KnowledgeDocumentRecord(
            id=value.id,
            title=value.title,
            original_filename=value.original_filename,
            file_hash=value.file_hash,
            business=value.business,
            document_type=value.document_type,
            region=value.region,
            access_scope=value.access_scope,
            workspace_id=value.workspace_id,
            authority=_enum_value(value.authority),
            version=value.version,
            effective_from=value.effective_from,
            effective_to=value.effective_to,
            status=_enum_value(value.status),
            file_path=value.file_path,
            page_count=value.page_count,
            chunk_count=value.chunk_count,
            error_message=value.error_message,
            created_at=value.created_at,
            updated_at=value.updated_at,
        )

    def create_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        saved = super().create_document(document)
        self._transaction(lambda session: session.merge(self._document_record(saved)))
        return saved

    def update_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        saved = super().update_document(document)
        self._transaction(lambda session: session.merge(self._document_record(saved)))
        return saved

    def replace_chunks(self, document_id: UUID, chunks: list[KnowledgeChunk]) -> None:
        super().replace_chunks(document_id, chunks)

        def persist(session: Session) -> None:
            session.execute(delete(KnowledgeChunkRecord).where(KnowledgeChunkRecord.document_id == document_id))
            for value in chunks:
                session.add(
                    KnowledgeChunkRecord(
                        id=value.id,
                        document_id=value.document_id,
                        chunk_index=value.chunk_index,
                        content=value.content,
                        lexical_content=value.lexical_content,
                        embedding=value.embedding,
                        chunk_type=_enum_value(value.chunk_type),
                        page_start=value.page_start,
                        page_end=value.page_end,
                        section_path=value.section_path,
                        content_hash=value.content_hash,
                        metadata_json=value.metadata,
                    )
                )

        self._transaction(persist)
