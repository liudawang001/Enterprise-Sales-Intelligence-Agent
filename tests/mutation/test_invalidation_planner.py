import pytest

from app.agent.enums import MutationScope
from app.criteria.models import CompiledConstraint, CriteriaDiff, RankingPreference
from app.mutation.models import ArtifactReuseContext, TaskDiff
from app.mutation.planner import TaskMutationPlanner


def _context(**updates):
    data = {
        "task_id": "task-1",
        "task_version": 4,
        "criteria_snapshot_id": "criteria-4",
        "search_plan_id": "plan-4",
        "raw_candidate_set_id": "raw-4",
        "raw_candidate_count": 120,
        "filtered_candidate_set_id": "filtered-4",
        "filtered_candidate_count": 90,
        "researched_candidate_set_id": "researched-4",
        "researched_candidate_count": 80,
        "verified_lead_set_id": "verified-4",
        "verified_lead_count": 80,
        "lead_score_set_id": "scores-4",
        "scored_lead_count": 50,
        "available_candidate_fields": {"industry", "employee_count", "region"},
        "available_verified_fields": {"industry", "employee_count", "website"},
        "discovery_pushdown_fields": {"industry"},
        "post_filter_fields": {"employee_count"},
        "enrichment_fields": {"website", "employee_count"},
        "field_dependencies": {"industry": ["DISCOVERY", "RANK"], "employee_count": ["FILTER"], "website": ["ENRICHMENT"]},
    }
    data.update(updates)
    return ArtifactReuseContext(**data)


def _plan(task_diff, criteria_diff=None, context=None, before=50, after=50, required=None):
    return TaskMutationPlanner().plan(task_diff, criteria_diff or CriteriaDiff(), context or _context(), base_version=4, next_version=5, before_target_count=before, after_target_count=after, newly_required_fields=required)


@pytest.mark.parametrize(
    ("after", "scored", "verified", "raw", "scope"),
    [(30, 80, 80, 120, "DISPLAY_ONLY"), (70, 80, 80, 120, "DISPLAY_ONLY"), (70, 50, 80, 120, "RANK_ONLY"), (100, 50, 80, 120, "FILTER_ONLY"), (200, 50, 80, 120, "DISCOVERY_REQUIRED")],
)
def test_target_count_uses_artifact_coverage(after, scored, verified, raw, scope):
    context = _context(scored_lead_count=scored, verified_lead_count=verified, raw_candidate_count=raw)
    assert _plan(TaskDiff(target_count_changed=True), context=context, after=after).scope == scope


def test_hard_post_filter_removal_filters_but_pushdown_removal_rediscovers():
    employee = CompiledConstraint(field="employee_count", operator="GTE", value=100)
    industry = CompiledConstraint(field="industry", operator="EQ", value="制造业")
    assert _plan(TaskDiff(constraint_fields_changed=["employee_count"], hard_constraints_changed=True), CriteriaDiff(removed_hard=[employee])).scope == MutationScope.FILTER_ONLY
    assert _plan(TaskDiff(constraint_fields_changed=["industry"], hard_constraints_changed=True), CriteriaDiff(removed_hard=[industry])).scope == MutationScope.DISCOVERY_REQUIRED


def test_soft_and_required_fields_use_verified_coverage():
    soft = RankingPreference(field="industry", operator="EQ", value="物流", normalized_weight=1)
    assert _plan(TaskDiff(soft_constraints_changed=True), CriteriaDiff(added_soft=[soft])).scope == MutationScope.RANK_ONLY
    assert _plan(TaskDiff(required_fields_changed=True), required={"website"}).scope == MutationScope.DISPLAY_ONLY
    assert _plan(TaskDiff(required_fields_changed=True), required={"public_phone"}).scope == MutationScope.ENRICHMENT_REQUIRED


def test_region_and_business_changes_have_fixed_safe_bounds():
    assert _plan(TaskDiff(region_changed=True)).scope == MutationScope.DISCOVERY_REQUIRED
    assert _plan(TaskDiff(business_changed=True)).scope == MutationScope.FULL_REPLAN


def test_runtime_can_record_safe_scope_escalation():
    plan = _plan(TaskDiff(constraint_fields_changed=["employee_count"], hard_constraints_changed=True), CriteriaDiff(added_hard=[CompiledConstraint(field="employee_count", operator="GTE", value=100)]))
    escalated = plan.model_copy(update={"final_scope": MutationScope.DISCOVERY_REQUIRED, "escalation_reason": "REUSABLE_RAW_POOL_MISSING"})
    assert escalated.original_scope == MutationScope.FILTER_ONLY
    assert escalated.final_scope == MutationScope.DISCOVERY_REQUIRED
    assert escalated.escalation_reason == "REUSABLE_RAW_POOL_MISSING"
