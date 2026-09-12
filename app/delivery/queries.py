from __future__ import annotations

from math import ceil
from typing import Any, ClassVar

from app.delivery.models import (
    DeliveryBundle,
    DeliveryLeadRow,
    DeliverySnapshot,
    EvidenceDTO,
    LeadDetailDTO,
    LeadPageDTO,
    ScoreExplainDTO,
    TaskSummaryDTO,
    TaskVersionDTO,
)


class DeliveryNotFoundError(ValueError):
    pass


class DeliveryQueryService:
    SORT_FIELDS: ClassVar[set[str]] = {
        "rank",
        "lead_score",
        "enterprise_name",
        "industry",
        "company_scale",
        "region",
        "office_count",
        "verification_status",
    }

    def __init__(self, deps: object, snapshot_repository: object) -> None:
        self.deps = deps
        self.snapshots = snapshot_repository

    def freeze(
        self,
        task_id: str,
        task_version: int | None = None,
        *,
        force_new: bool = False,
    ) -> DeliveryBundle:
        task = self.deps.task_repository.get_task(task_id)
        if not task:
            raise DeliveryNotFoundError("TASK_NOT_FOUND")
        version = task.version if task_version is None else task_version
        task_version_model = self.deps.task_repository.get_version(task_id, version)
        if not task_version_model:
            raise DeliveryNotFoundError("TASK_VERSION_NOT_FOUND")
        execution = self.deps.execution_snapshot_repository.for_version(task_id, version)
        if not execution:
            raise DeliveryNotFoundError("EXECUTION_SNAPSHOT_NOT_FOUND")
        if not execution.lead_score_set_id:
            raise DeliveryNotFoundError("LEAD_SCORE_SET_NOT_FOUND")
        if not execution.verified_lead_set_id:
            raise DeliveryNotFoundError("VERIFIED_LEAD_SET_NOT_FOUND")
        if not force_new:
            cached = self.snapshots.for_execution(
                task_id, version, execution.snapshot_id
            )
            if cached:
                return cached

        lead_set = self.deps.lead_score_repository.get_lead_set(
            execution.lead_score_set_id
        )
        if not lead_set:
            raise DeliveryNotFoundError("LEAD_SCORE_SET_NOT_FOUND")
        scores = self.deps.lead_score_repository.scores_for_set(lead_set)
        score_by_enterprise = {item.enterprise_id: item for item in scores}
        snapshot = DeliverySnapshot(
            task_id=task_id,
            task_version=version,
            criteria_snapshot_id=execution.criteria_snapshot_id,
            verified_lead_set_id=execution.verified_lead_set_id,
            lead_score_set_id=execution.lead_score_set_id,
            scoring_profile_id=execution.scoring_profile_id,
            result_count=len(lead_set.lead_ids),
            execution_snapshot_id=execution.snapshot_id,
        )
        active = self.deps.task_repository.get_active_task(task.session_id)
        criteria = self.deps.rule_service.repository.criteria.get(
            execution.criteria_snapshot_id or ""
        )
        hard_constraints = (
            [item.model_dump(mode="json") for item in criteria.hard_constraints]
            if criteria
            else []
        )
        soft_preferences = (
            [item.model_dump(mode="json") for item in criteria.ranking_preferences]
            if criteria
            else []
        )
        task_dto = TaskSummaryDTO(
            task_id=task_id,
            session_id=task.session_id,
            business=task_version_model.business,
            region=task_version_model.region,
            target_count=task_version_model.target_count,
            status=task.status.value,
            stage=task.stage.value,
            active=bool(active and active.task_id == task_id),
            current_version=task.version,
            viewed_version=version,
            historical=version != task.version,
            result_count=len(lead_set.lead_ids),
            updated_at=task.updated_at,
            criteria_snapshot_id=execution.criteria_snapshot_id,
            verified_lead_set_id=execution.verified_lead_set_id,
            lead_score_set_id=execution.lead_score_set_id,
            current_mutation_scope=self._latest_mutation_scope(task_id),
            hard_constraints=hard_constraints,
            soft_preferences=soft_preferences,
        )
        leads: list[DeliveryLeadRow] = []
        details: dict[str, LeadDetailDTO] = {}
        for index, enterprise_id in enumerate(lead_set.lead_ids, start=1):
            score = score_by_enterprise.get(enterprise_id)
            if not score:
                continue
            profile = self._profile_for_score(score)
            enterprise = self.deps.enterprise_repository.get_enterprise(enterprise_id)
            evidence, evidence_by_id = self._evidence_for_profile(profile, score)
            reason = self.deps.lead_score_repository.reason_for_score(score)
            row = self._lead_row(
                index,
                task_version_model.business or "",
                enterprise,
                profile,
                score,
                reason,
                evidence_by_id,
            )
            score_dto = ScoreExplainDTO(
                enterprise_id=enterprise_id,
                lead_score_id=score.lead_score_id,
                total_score=score.total_score,
                rank_status=score.rank_status.value,
                verification_status=score.verification_status,
                evidence_coverage=score.evidence_coverage,
                scoring_profile_id=score.scoring_profile_id,
                scoring_profile_version=score.scoring_profile_version,
                components=[
                    item.model_dump(mode="json") for item in score.component_scores
                ],
                recommendation_reason=reason.summary if reason else None,
                reason_codes=reason.reason_codes if reason else [],
                evidence_ids=reason.evidence_ids if reason else [],
            )
            resolved_fields = (
                [item.model_dump(mode="json") for item in profile.fields.values()]
                if profile
                else []
            )
            details[enterprise_id] = LeadDetailDTO(
                snapshot_id=snapshot.snapshot_id,
                task_id=task_id,
                task_version=version,
                score_set_id=execution.lead_score_set_id,
                lead=row,
                enterprise_profile=enterprise.model_dump(mode="json")
                if enterprise
                else {"enterprise_id": enterprise_id},
                relations=[
                    item.model_dump(mode="json")
                    for item in self.deps.enterprise_repository.list_relations(
                        enterprise_id
                    )
                ],
                locations=[
                    item.model_dump(mode="json")
                    for item in self.deps.enterprise_repository.locations.values()
                    if item.enterprise_id == enterprise_id
                ],
                resolved_fields=resolved_fields,
                score=score_dto,
                evidence=evidence,
            )
            leads.append(row)
        snapshot = snapshot.model_copy(update={"result_count": len(leads)})
        bundle = DeliveryBundle(
            snapshot=snapshot, task=task_dto, leads=leads, details=details
        )
        return self.snapshots.save(bundle)

    def get_bundle(self, snapshot_id: str) -> DeliveryBundle:
        value = self.snapshots.get(snapshot_id)
        if not value:
            raise DeliveryNotFoundError("DELIVERY_SNAPSHOT_NOT_FOUND")
        return value

    def list_tasks(self, session_id: str | None = None) -> list[TaskSummaryDTO]:
        result = []
        for task in reversed(self.deps.task_repository.list_tasks(session_id)):
            execution = self.deps.execution_snapshot_repository.current(task.task_id)
            active = self.deps.task_repository.get_active_task(task.session_id)
            lead_set = (
                self.deps.lead_score_repository.get_lead_set(
                    execution.lead_score_set_id
                )
                if execution and execution.lead_score_set_id
                else None
            )
            result.append(
                TaskSummaryDTO(
                    task_id=task.task_id,
                    session_id=task.session_id,
                    business=task.business,
                    region=task.region,
                    target_count=task.target_count,
                    status=task.status.value,
                    stage=task.stage.value,
                    active=bool(active and active.task_id == task.task_id),
                    current_version=task.version,
                    viewed_version=task.version,
                    historical=False,
                    result_count=lead_set.lead_count if lead_set else 0,
                    updated_at=task.updated_at,
                    criteria_snapshot_id=execution.criteria_snapshot_id
                    if execution
                    else None,
                    verified_lead_set_id=execution.verified_lead_set_id
                    if execution
                    else None,
                    lead_score_set_id=execution.lead_score_set_id
                    if execution
                    else None,
                    current_mutation_scope=self._latest_mutation_scope(task.task_id),
                )
            )
        return result

    def task_version(self, task_id: str, version: int) -> TaskVersionDTO:
        task = self.deps.task_repository.get_task(task_id)
        value = self.deps.task_repository.get_version(task_id, version)
        if not task or not value:
            raise DeliveryNotFoundError("TASK_VERSION_NOT_FOUND")
        return TaskVersionDTO(
            **value.model_dump(), read_only=version != task.version
        )

    def lead_page(
        self,
        task_id: str,
        version: int,
        *,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "rank",
        sort_order: str = "asc",
        verification_status: str | None = None,
        min_score: float | None = None,
        industry: str | None = None,
        has_public_phone: bool | None = None,
        has_website: bool | None = None,
    ) -> LeadPageDTO:
        if sort_by not in self.SORT_FIELDS:
            raise ValueError("INVALID_SORT_FIELD")
        if sort_order not in {"asc", "desc"}:
            raise ValueError("INVALID_SORT_ORDER")
        bundle = self.freeze(task_id, version)
        items = [
            item
            for item in bundle.leads
            if (not verification_status or item.verification_status == verification_status)
            and (min_score is None or (item.lead_score is not None and item.lead_score >= min_score))
            and (not industry or item.industry == industry)
            and (has_public_phone is None or bool(item.public_phone) == has_public_phone)
            and (has_website is None or bool(item.website) == has_website)
        ]
        if sort_by != "rank":
            reverse = sort_order == "desc"
            items.sort(
                key=lambda item: (
                    getattr(item, sort_by) is None,
                    getattr(item, sort_by),
                    item.enterprise_id,
                ),
                reverse=reverse,
            )
        elif sort_order == "desc":
            items.reverse()
        total = len(items)
        start = (page - 1) * page_size
        page_items = items[start : start + page_size]
        counts = {
            status: sum(1 for item in items if item.verification_status == status)
            for status in ("VERIFIED", "PARTIAL", "CONFLICTING", "UNVERIFIED")
        }
        counts["evidence_coverage"] = round(
            sum(item.evidence_confidence or 0 for item in items) / total, 4
        ) if total else 0.0
        counts["contact_completeness"] = round(
            sum(bool(item.public_phone or item.website) for item in items) / total, 4
        ) if total else 0.0
        return LeadPageDTO(
            snapshot_id=bundle.snapshot.snapshot_id,
            task_id=task_id,
            task_version=version,
            score_set_id=bundle.snapshot.lead_score_set_id,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
            sort_by=sort_by,
            sort_order=sort_order,
            view_sort=sort_by != "rank",
            items=page_items,
            quality_summary=counts,
        )

    def _profile_for_score(self, score: object):
        profiles = [
            item
            for item in self.deps.evidence_repository.profiles.values()
            if item.enterprise_id == score.enterprise_id
            and item.updated_at <= score.created_at
        ]
        if not profiles:
            return None
        score_evidence = {
            evidence_id
            for component in score.component_scores
            for evidence_id in component.evidence_ids
        }

        def profile_key(profile: object) -> tuple[int, Any]:
            profile_ids = {
                evidence_id
                for field in profile.fields.values()
                for evidence_id in (
                    field.supporting_evidence_ids + field.conflicting_evidence_ids
                )
            }
            return (len(score_evidence & profile_ids), profile.updated_at)

        return max(profiles, key=profile_key)

    def _evidence_for_profile(self, profile: object, score: object):
        roles: dict[str, str] = {}
        if profile:
            for field in profile.fields.values():
                roles.update({item: "SUPPORTING" for item in field.supporting_evidence_ids})
                roles.update({item: "CONFLICTING" for item in field.conflicting_evidence_ids})
        for component in score.component_scores:
            roles.update({item: roles.get(item, "SUPPORTING") for item in component.evidence_ids})
        values = []
        by_id = {}
        for evidence_id, role in roles.items():
            item = self.deps.evidence_repository.evidence.get(evidence_id)
            if not item:
                continue
            by_id[evidence_id] = item
            values.append(
                EvidenceDTO(
                    evidence_id=item.evidence_id,
                    enterprise_id=item.enterprise_id,
                    field_name=item.field_name,
                    value=item.value,
                    normalized_value=item.normalized_value,
                    verification_role=role,
                    provider=item.provider,
                    source_type=item.source_type.value,
                    source_record_id=item.source_record_id,
                    source_url=item.source_url,
                    retrieved_at=item.retrieved_at,
                    confidence=item.confidence,
                )
            )
        values.sort(key=lambda item: (item.field_name, item.verification_role, item.evidence_id))
        return values, by_id

    def _lead_row(
        self,
        rank: int,
        business: str,
        enterprise: object,
        profile: object,
        score: object,
        reason: object,
        evidence_by_id: dict[str, object],
    ) -> DeliveryLeadRow:
        fields = profile.fields if profile else {}

        def value(*names: str):
            for name in names:
                field = fields.get(name)
                if field and field.primary_value is not None:
                    return field.primary_value
            return None

        parent = None
        if enterprise and enterprise.parent_enterprise_id:
            parent_value = self.deps.enterprise_repository.get_enterprise(
                enterprise.parent_enterprise_id
            )
            parent = parent_value.canonical_name if parent_value else None
        source_ids = []
        for name in ("public_phone", "website", "address", "company_name"):
            field = fields.get(name)
            if field:
                source_ids.extend(field.supporting_evidence_ids)
        primary_evidence = next(
            (evidence_by_id[item] for item in source_ids if item in evidence_by_id),
            next(iter(evidence_by_id.values()), None),
        )
        statuses = {name: field.status.value for name, field in fields.items()}
        address = value("address", "office_address", "office_location")
        return DeliveryLeadRow(
            rank=rank,
            enterprise_id=score.enterprise_id,
            enterprise_name=enterprise.canonical_name if enterprise else score.enterprise_id,
            parent_enterprise=parent,
            industry=value("industry"),
            company_scale=value("company_scale", "basic_scale"),
            region=value("region") or (enterprise.primary_region if enterprise else None),
            office_count=value("office_count"),
            office_address=str(address) if address is not None else None,
            public_phone=value("public_phone", "phone"),
            website=value("website") or (enterprise.primary_website if enterprise else None),
            recommended_business=business,
            lead_score=score.total_score,
            score_status=score.rank_status.value,
            verification_status=score.verification_status,
            evidence_confidence=score.evidence_coverage,
            recommendation_reason=reason.summary if reason else None,
            primary_source=primary_evidence.source_type.value if primary_evidence else None,
            primary_source_url=primary_evidence.source_url if primary_evidence else None,
            verified_at=profile.updated_at if profile else None,
            field_statuses=statuses,
        )

    def _latest_mutation_scope(self, task_id: str) -> str | None:
        repository = getattr(self.deps, "mutation_repository", None)
        if not repository:
            return None
        values = [
            item for item in repository.mutations.values() if item.task_id == task_id
        ]
        return values[-1].scope.value if values and values[-1].scope else None
