from __future__ import annotations

from app.mutation.models import ArtifactReuseContext


def _complete_fields(items: list[dict]) -> set[str]:
    if not items:
        return set()
    sets = [{key for key, value in item.items() if value not in (None, "", [], {})} for item in items]
    return set.intersection(*sets) if sets else set()


def _complete_verified_fields(items: list[dict]) -> set[str]:
    if not items:
        return set()
    complete = []
    for fields in items:
        complete.append(
            {
                field_name
                for field_name, resolved in fields.items()
                if isinstance(resolved, dict)
                and resolved.get("primary_value") not in (None, "", [], {})
                and resolved.get("status") != "MISSING"
            }
        )
    return set.intersection(*complete) if complete else set()


class ArtifactReuseAnalyzer:
    def __init__(self, deps) -> None:
        self.deps = deps

    def analyze(self, task_id: str, task_version: int) -> ArtifactReuseContext:
        snapshot = self.deps.execution_snapshot_repository.current(task_id)
        if not snapshot:
            return ArtifactReuseContext(task_id=task_id, task_version=task_version)
        research_repo = self.deps.research_service.repository
        raw = research_repo.get_candidates(snapshot.raw_candidate_set_id)
        filtered = research_repo.get_candidates(snapshot.filtered_candidate_set_id)
        researched = research_repo.get_candidates(snapshot.researched_candidate_set_id)
        plan = research_repo.plans.get(snapshot.search_plan_id or "")
        profile_ids = []
        lead_set = (
            self.deps.lead_score_repository.lead_sets.get(snapshot.lead_score_set_id or "")
            if self.deps.lead_score_repository
            else None
        )
        if self.deps.evidence_repository:
            run = self.deps.evidence_repository.latest_run_for_task(task_id)
            profile_ids = list(run.profile_ids) if run else []
        profiles = (
            [
                self.deps.evidence_repository.profiles[item].model_dump(mode="json")
                for item in profile_ids
                if item in self.deps.evidence_repository.profiles
            ]
            if self.deps.evidence_repository
            else []
        )
        pushdown_fields: set[str] = set()
        enrichment_fields: set[str] = set()
        if plan:
            for value in plan.pushdown_explain.values():
                pushdown_fields.update(value.get("provider_filters", []))
                enrichment_fields.update(value.get("enrichment_requirements", []))
        return ArtifactReuseContext(
            task_id=task_id,
            task_version=task_version,
            criteria_snapshot_id=snapshot.criteria_snapshot_id,
            search_plan_id=snapshot.search_plan_id,
            raw_candidate_set_id=snapshot.raw_candidate_set_id,
            raw_candidate_count=len(raw),
            filtered_candidate_set_id=snapshot.filtered_candidate_set_id,
            filtered_candidate_count=len(filtered),
            researched_candidate_set_id=snapshot.researched_candidate_set_id,
            researched_candidate_count=len(researched),
            verified_lead_set_id=snapshot.verified_lead_set_id,
            verified_lead_count=len(profile_ids),
            lead_score_set_id=snapshot.lead_score_set_id,
            scored_lead_count=lead_set.lead_count if lead_set else 0,
            scoring_profile_id=snapshot.scoring_profile_id,
            available_candidate_fields=_complete_fields([item.model_dump(mode="json") for item in (raw or researched)]),
            available_verified_fields=_complete_verified_fields([value.get("fields", {}) for value in profiles]),
            discovery_pushdown_fields=pushdown_fields,
            post_filter_fields=set(plan.post_filter_fields) if plan else set(),
            enrichment_fields=enrichment_fields
            | (set(plan.cheap_enrichment_fields + plan.deep_research_fields) if plan else set()),
            field_dependencies=dict(plan.field_dependencies) if plan else {},
        )
