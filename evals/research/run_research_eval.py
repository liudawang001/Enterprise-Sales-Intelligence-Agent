from app.criteria.models import CompiledConstraint, LeadCriteria
from app.providers.fakes import (
    FakeEnterpriseProvider,
    FakeMapProvider,
    FakeWebSearchProvider,
)
from app.research.models import ResearchBudget
from app.research.planner import SearchPlanner, SearchPlanValidator


def _criteria(index: int) -> LeadCriteria:
    return LeadCriteria(
        task_id=f"plan-{index}",
        task_version=1,
        business_code="GROUP_VNET",
        region_scope=["上海松江"],
        target_count=(index % 10) + 1,
        hard_constraints=[
            CompiledConstraint(field="region", operator="EQ", value="上海松江"),
            CompiledConstraint(field="industry", operator="EQ", value="制造业"),
            CompiledConstraint(field="office_count", operator="GTE", value=2),
        ],
    )


def run() -> dict[str, float]:
    caps = {
        "enterprise": FakeEnterpriseProvider.capabilities,
        "map": FakeMapProvider.capabilities,
        "web_search": FakeWebSearchProvider.capabilities,
    }
    planner = SearchPlanner(caps, budget=ResearchBudget(max_candidates=100))
    validator = SearchPlanValidator(
        set(caps), set().union(*(v.supported_fields for v in caps.values()))
    )
    planning_cases = [_criteria(i) for i in range(30)]
    pushdown_cases = [_criteria(i) for i in range(20)]
    budget_failure_cases = [_criteria(i) for i in range(20)]
    plans = [planner.build(case) for case in planning_cases]
    valid = sum(1 for plan in plans if not validator.validate(plan))
    coverage = sum(
        1
        for case in pushdown_cases
        if set(planner.build(case).post_filter_fields)
        | set(planner.build(case).pushdown_explain["enterprise"]["provider_filters"])
        >= {"region", "industry", "office_count"}
    )
    budget_valid = sum(
        1
        for case in budget_failure_cases
        if planner.build(case).candidate_target <= 100
    )
    return {
        "search_plan_schema_validity": valid / 30,
        "hard_constraint_coverage": coverage / 20,
        "budget_validity": budget_valid / 20,
        "case_count": 70,
    }


if __name__ == "__main__":
    for key, value in run().items():
        print(f"{key}: {value:.3f}")
