from __future__ import annotations

from copy import deepcopy
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.enums import EntityRelationType
from app.entities.models import (
    CanonicalEnterprise,
    EnterpriseCandidateLink,
    EnterpriseLocation,
    EnterpriseRelation,
    EntityResolutionRun,
    ResolutionDecision,
)
from app.persistence.models.verification import (
    CanonicalEnterpriseRecord,
    EnterpriseCandidateLinkRecord,
    EnterpriseLocationRecord,
    EnterpriseRelationRecord,
    EntityResolutionDecisionRecord,
    EntityResolutionRunRecord,
)


class InMemoryEnterpriseRepository:
    def __init__(self, research_repository) -> None:
        self.research_repository = research_repository
        self.resolution_runs: dict[str, EntityResolutionRun] = {}
        self.enterprises: dict[str, CanonicalEnterprise] = {}
        self.candidate_links: dict[str, EnterpriseCandidateLink] = {}
        self.relations: dict[str, EnterpriseRelation] = {}
        self.locations: dict[str, EnterpriseLocation] = {}
        self.resolution_audits: dict[str, list[ResolutionDecision]] = {}

    def save_resolution_run(self, value: EntityResolutionRun) -> EntityResolutionRun:
        self.resolution_runs[value.resolution_run_id] = deepcopy(value)
        return deepcopy(value)

    def save_enterprise(self, value: CanonicalEnterprise) -> CanonicalEnterprise:
        self.enterprises[value.enterprise_id] = deepcopy(value)
        return deepcopy(value)

    def save_candidate_link(self, value: EnterpriseCandidateLink) -> EnterpriseCandidateLink:
        self.candidate_links[value.candidate_id] = deepcopy(value)
        return deepcopy(value)

    def save_location(self, value: EnterpriseLocation) -> EnterpriseLocation:
        existing = next(
            (
                item
                for item in self.locations.values()
                if item.enterprise_id == value.enterprise_id
                and item.normalized_address == value.normalized_address
            ),
            None,
        )
        if existing:
            merged = existing.model_copy(
                update={
                    "evidence_ids": list(
                        dict.fromkeys(existing.evidence_ids + value.evidence_ids)
                    )
                }
            )
            self.locations[existing.location_id] = deepcopy(merged)
            return deepcopy(merged)
        self.locations[value.location_id] = deepcopy(value)
        return deepcopy(value)

    def save_resolution_decision(self, run_id: str, value: ResolutionDecision) -> None:
        self.resolution_audits.setdefault(run_id, []).append(deepcopy(value))

    def materialize_relations(
        self,
        decisions: list[ResolutionDecision],
        enterprise_by_candidate: dict[str, CanonicalEnterprise],
    ) -> None:
        seen: set[tuple[str, str, str]] = set()
        for decision in decisions:
            if decision.relation == EntityRelationType.SAME_ENTITY:
                continue
            left = enterprise_by_candidate[decision.left_candidate_id]
            right = enterprise_by_candidate[decision.right_candidate_id]
            if left.enterprise_id == right.enterprise_id:
                continue
            key = (left.enterprise_id, right.enterprise_id, decision.relation.value)
            if key in seen:
                continue
            seen.add(key)
            relation = EnterpriseRelation(
                from_enterprise_id=left.enterprise_id,
                to_enterprise_id=right.enterprise_id,
                relation_type=decision.relation,
                confidence=decision.confidence,
            )
            self.relations[relation.relation_id] = relation

    def get_enterprise(self, enterprise_id: str) -> CanonicalEnterprise | None:
        value = self.enterprises.get(enterprise_id)
        return deepcopy(value) if value else None

    def list_for_task(self, task_id: str) -> list[CanonicalEnterprise]:
        run_ids = {
            item.resolution_run_id
            for item in self.resolution_runs.values()
            if item.task_id == task_id
        }
        enterprise_ids = {
            link.enterprise_id
            for link in self.candidate_links.values()
            if link.resolution_run_id in run_ids
        }
        return [deepcopy(value) for key, value in self.enterprises.items() if key in enterprise_ids]

    def list_relations(self, enterprise_id: str) -> list[EnterpriseRelation]:
        return [
            deepcopy(value)
            for value in self.relations.values()
            if enterprise_id in {value.from_enterprise_id, value.to_enterprise_id}
        ]

    def latest_run_for_task(self, task_id: str) -> EntityResolutionRun | None:
        values = [value for value in self.resolution_runs.values() if value.task_id == task_id]
        return deepcopy(values[-1]) if values else None


class EnterpriseRepository:
    """PostgreSQL adapter for canonical entities and auditable resolution facts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_resolution_run(self, value: EntityResolutionRun) -> EntityResolutionRun:
        record = await self.session.get(EntityResolutionRunRecord, UUID(value.resolution_run_id))
        fields = {
            "task_id": value.task_id,
            "candidate_set_id": UUID(value.researched_candidate_set_id),
            "status": value.status,
            "rule_version": value.rule_version,
            "candidate_count": value.candidate_count,
            "enterprise_count": value.enterprise_count,
            "started_at": value.started_at,
            "finished_at": value.finished_at,
        }
        if record:
            for key, item in fields.items():
                setattr(record, key, item)
        else:
            self.session.add(EntityResolutionRunRecord(id=UUID(value.resolution_run_id), **fields))
        await self.session.flush()
        return value

    async def save_enterprise(self, value: CanonicalEnterprise) -> CanonicalEnterprise:
        record = await self.session.get(CanonicalEnterpriseRecord, UUID(value.enterprise_id))
        fields = {
            "canonical_name": value.canonical_name,
            "entity_type": value.entity_type.value,
            "parent_enterprise_id": UUID(value.parent_enterprise_id)
            if value.parent_enterprise_id
            else None,
            "unified_social_credit_code": value.unified_social_credit_code,
            "primary_region": value.primary_region,
            "primary_website": value.primary_website,
            "resolution_status": value.resolution_status.value,
            "resolution_confidence": value.resolution_confidence,
            "created_at": value.created_at,
            "updated_at": value.updated_at,
        }
        if record:
            for key, item in fields.items():
                setattr(record, key, item)
        else:
            self.session.add(CanonicalEnterpriseRecord(id=UUID(value.enterprise_id), **fields))
        await self.session.flush()
        return value

    async def save_candidate_link(self, value: EnterpriseCandidateLink) -> EnterpriseCandidateLink:
        key = (UUID(value.enterprise_id), UUID(value.candidate_id))
        if not await self.session.get(EnterpriseCandidateLinkRecord, key):
            self.session.add(EnterpriseCandidateLinkRecord(enterprise_id=key[0], candidate_id=key[1], resolution_run_id=UUID(value.resolution_run_id), decision=value.decision.value, confidence=value.confidence, created_at=value.created_at))
            await self.session.flush()
        return value

    async def save_resolution_decision(self, run_id: str, value: ResolutionDecision) -> None:
        self.session.add(EntityResolutionDecisionRecord(id=uuid4(), resolution_run_id=UUID(run_id), left_candidate_id=UUID(value.left_candidate_id), right_candidate_id=UUID(value.right_candidate_id), relation=value.relation.value, confidence=value.confidence, audit_json=value.model_dump(mode="json")))
        await self.session.flush()

    async def save_relation(self, value: EnterpriseRelation) -> EnterpriseRelation:
        if not await self.session.get(EnterpriseRelationRecord, UUID(value.relation_id)):
            self.session.add(EnterpriseRelationRecord(id=UUID(value.relation_id), from_enterprise_id=UUID(value.from_enterprise_id), to_enterprise_id=UUID(value.to_enterprise_id), relation_type=value.relation_type.value, confidence=value.confidence, evidence_ids=value.evidence_ids, created_at=value.created_at))
            await self.session.flush()
        return value

    async def save_location(self, value: EnterpriseLocation) -> EnterpriseLocation:
        if not await self.session.get(EnterpriseLocationRecord, UUID(value.location_id)):
            self.session.add(EnterpriseLocationRecord(id=UUID(value.location_id), enterprise_id=UUID(value.enterprise_id), location_type=value.location_type.value, address=value.address, normalized_address=value.normalized_address, lat=value.lat, lng=value.lng, evidence_ids=value.evidence_ids, verification_status=value.verification_status))
            await self.session.flush()
        return value
