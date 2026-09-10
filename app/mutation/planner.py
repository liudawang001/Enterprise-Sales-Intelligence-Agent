from __future__ import annotations

from app.agent.enums import MutationScope
from app.criteria.models import CriteriaDiff
from app.mutation.invalidation import classify_invalidation
from app.mutation.models import (
    ArtifactReuseContext,
    ReexecutionPlan,
    ReuseDecision,
    TaskDiff,
)

_PATHS = {
    MutationScope.NONE: ("COMPOSE", ["reuse_current_snapshot", "compose_lead_response"]),
    MutationScope.DISPLAY_ONLY: ("PROJECTION", ["select_existing_leads", "compose_lead_response"]),
    MutationScope.RANK_ONLY: ("SCORING", ["reuse_verified_profiles", "score_leads", "compose_lead_response"]),
    MutationScope.FILTER_ONLY: ("FILTER", ["select_reusable_candidate_pool", "filter_existing", "plan_verification_reuse", "verify_new_or_affected", "score_leads", "compose_lead_response"]),
    MutationScope.ENRICHMENT_REQUIRED: ("ENRICHMENT", ["select_reusable_entities", "targeted_enrichment", "verify_affected", "score_leads", "compose_lead_response"]),
    MutationScope.DISCOVERY_REQUIRED: ("DISCOVERY", ["reuse_business_planning", "research", "verification", "score_leads", "compose_lead_response"]),
    MutationScope.FULL_REPLAN: ("BUSINESS_PLANNING", ["business_planning", "research", "verification", "score_leads", "compose_lead_response"]),
}


class TaskMutationPlanner:
    def plan(
        self,
        task_diff: TaskDiff,
        criteria_diff: CriteriaDiff,
        reuse_context: ArtifactReuseContext,
        *,
        base_version: int,
        next_version: int,
        before_target_count: int | None = None,
        after_target_count: int | None = None,
        newly_required_fields: set[str] | None = None,
    ) -> ReexecutionPlan:
        scope, reasons = classify_invalidation(
            task_diff,
            criteria_diff,
            reuse_context,
            before_target_count=before_target_count,
            after_target_count=after_target_count,
            newly_required_fields=newly_required_fields,
        )
        start_stage, steps = _PATHS[scope]
        artifacts = [
            reuse_context.criteria_snapshot_id,
            reuse_context.search_plan_id,
            reuse_context.raw_candidate_set_id,
            reuse_context.filtered_candidate_set_id,
            reuse_context.researched_candidate_set_id,
            reuse_context.verified_lead_set_id,
            reuse_context.lead_score_set_id,
        ]
        reusable = [item for item in artifacts if item]
        decisions = self._decisions(scope)
        invalidated = [artifact for key, artifact in zip(("criteria", "search_plan", "raw_candidates", "filtered_candidates", "researched_candidates", "verified", "scores"), artifacts) if artifact and decisions.get(key) == ReuseDecision.REBUILD]
        return ReexecutionPlan(
            task_id=reuse_context.task_id,
            base_version=base_version,
            next_version=next_version,
            original_scope=scope,
            final_scope=scope,
            start_stage=start_stage,
            steps=steps,
            reused_artifact_ids=[artifact for artifact in reusable if artifact not in invalidated],
            invalidated_artifact_ids=invalidated,
            required_fields=sorted(newly_required_fields or set()),
            reason_codes=reasons,
            reuse_decisions=decisions,
            estimated_external_calls=0 if scope in {MutationScope.NONE, MutationScope.DISPLAY_ONLY, MutationScope.RANK_ONLY, MutationScope.FILTER_ONLY} else None,
        )

    @staticmethod
    def _decisions(scope: MutationScope) -> dict[str, ReuseDecision]:
        reuse = ReuseDecision.REUSE
        rebuild = ReuseDecision.REBUILD
        if scope in {MutationScope.NONE, MutationScope.DISPLAY_ONLY}:
            return {key: reuse for key in ("criteria", "search_plan", "raw_candidates", "filtered_candidates", "researched_candidates", "verified", "scores")}
        if scope == MutationScope.RANK_ONLY:
            return {"criteria": rebuild, "search_plan": reuse, "raw_candidates": reuse, "filtered_candidates": reuse, "researched_candidates": reuse, "verified": reuse, "scores": rebuild}
        if scope == MutationScope.FILTER_ONLY:
            return {"criteria": rebuild, "search_plan": reuse, "raw_candidates": reuse, "filtered_candidates": rebuild, "researched_candidates": reuse, "verified": ReuseDecision.REVERIFY, "scores": rebuild}
        if scope == MutationScope.ENRICHMENT_REQUIRED:
            return {"criteria": rebuild, "search_plan": reuse, "raw_candidates": reuse, "filtered_candidates": reuse, "researched_candidates": ReuseDecision.EXTEND, "verified": ReuseDecision.REVERIFY, "scores": rebuild}
        if scope == MutationScope.DISCOVERY_REQUIRED:
            return {"criteria": rebuild, "search_plan": rebuild, "raw_candidates": rebuild, "filtered_candidates": rebuild, "researched_candidates": rebuild, "verified": rebuild, "scores": rebuild}
        return {key: rebuild for key in ("criteria", "search_plan", "raw_candidates", "filtered_candidates", "researched_candidates", "verified", "scores")}
