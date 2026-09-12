from __future__ import annotations

from app.agent.enums import MutationScope
from app.criteria.models import CriteriaDiff
from app.mutation.models import ArtifactReuseContext, TaskDiff


def _criteria_fields(diff: CriteriaDiff, kind: str) -> set[str]:
    values = []
    for name in (f"added_{kind}", f"removed_{kind}"):
        values.extend(getattr(diff, name))
    changed = getattr(diff, f"changed_{kind}")
    return {item.field for item in values} | {item["field"] for item in changed}


def classify_invalidation(
    task_diff: TaskDiff,
    criteria_diff: CriteriaDiff,
    reuse: ArtifactReuseContext,
    *,
    before_target_count: int | None = None,
    after_target_count: int | None = None,
    newly_required_fields: set[str] | None = None,
) -> tuple[MutationScope, list[str]]:
    if not any(task_diff.model_dump().values()) and not any(criteria_diff.model_dump().values()):
        return MutationScope.NONE, ["NO_EFFECT"]
    if task_diff.business_changed or criteria_diff.business_changed:
        return MutationScope.FULL_REPLAN, ["BUSINESS_CHANGED"]
    if task_diff.region_changed or criteria_diff.region_changed:
        return MutationScope.DISCOVERY_REQUIRED, ["REGION_CHANGED", "DISCOVERY_UNIVERSE_CHANGED"]

    requested = newly_required_fields or set()
    if requested:
        if requested <= reuse.available_verified_fields:
            return MutationScope.DISPLAY_ONLY, ["REQUIRED_FIELD_ALREADY_AVAILABLE"]
        return MutationScope.ENRICHMENT_REQUIRED, ["REQUIRED_FIELD_NEEDS_ENRICHMENT"]

    hard_fields = _criteria_fields(criteria_diff, "hard")
    removed_hard = {item.field for item in criteria_diff.removed_hard}
    for item in criteria_diff.changed_hard:
        if item.get("before") and not item.get("after"):
            removed_hard.add(item["field"])
    if removed_hard & reuse.discovery_pushdown_fields:
        return MutationScope.DISCOVERY_REQUIRED, ["HARD_FILTER_WAS_DISCOVERY_PUSHDOWN", "DISCOVERY_UNIVERSE_CHANGED"]
    if hard_fields:
        dependency_discovery = {field for field in hard_fields if "DISCOVERY" in reuse.field_dependencies.get(field, [])}
        if dependency_discovery and not hard_fields <= reuse.available_candidate_fields:
            return MutationScope.DISCOVERY_REQUIRED, ["DISCOVERY_UNIVERSE_CHANGED"]
        if hard_fields <= reuse.available_candidate_fields:
            reason = "HARD_FILTER_REMOVED_POST_FILTER_ONLY" if removed_hard else "HARD_FILTER_FIELD_AVAILABLE"
            return MutationScope.FILTER_ONLY, [reason]
        enrichable = hard_fields <= (reuse.enrichment_fields | {field for field, stages in reuse.field_dependencies.items() if "ENRICHMENT" in stages})
        if enrichable:
            return MutationScope.ENRICHMENT_REQUIRED, ["HARD_FILTER_FIELD_MISSING"]
        return MutationScope.DISCOVERY_REQUIRED, ["ARTIFACT_COVERAGE_UNKNOWN"]

    soft_fields = _criteria_fields(criteria_diff, "soft")
    if soft_fields:
        if soft_fields <= reuse.available_verified_fields:
            return MutationScope.RANK_ONLY, ["SOFT_CRITERIA_CHANGED", "SCORING_INPUT_CHANGED"]
        return MutationScope.ENRICHMENT_REQUIRED, ["SOFT_CRITERIA_CHANGED", "REQUIRED_FIELD_NEEDS_ENRICHMENT"]

    if task_diff.target_count_changed and after_target_count is not None:
        if before_target_count is not None and after_target_count < before_target_count:
            return MutationScope.DISPLAY_ONLY, ["TARGET_COUNT_DECREASE"]
        if after_target_count <= reuse.scored_lead_count:
            return MutationScope.DISPLAY_ONLY, ["TARGET_COUNT_WITHIN_SCORED_POOL"]
        if after_target_count <= reuse.verified_lead_count:
            return MutationScope.RANK_ONLY, ["TARGET_COUNT_WITHIN_VERIFIED_POOL"]
        if after_target_count <= max(reuse.researched_candidate_count, reuse.filtered_candidate_count, reuse.raw_candidate_count):
            return MutationScope.FILTER_ONLY, ["HARD_FILTER_FIELD_AVAILABLE"]
        return MutationScope.DISCOVERY_REQUIRED, ["TARGET_COUNT_EXCEEDS_REUSABLE_POOL", "DISCOVERY_UNIVERSE_CHANGED"]

    if task_diff.export_fields_changed:
        return MutationScope.DISPLAY_ONLY, ["DISPLAY_FIELDS_ONLY"]
    return MutationScope.DISCOVERY_REQUIRED, ["ARTIFACT_COVERAGE_UNKNOWN"]
