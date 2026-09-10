import pytest

from app.criteria.models import CompiledConstraint, LeadCriteria
from app.providers.fakes import (
    FakeEnterpriseProvider,
    FakeMapProvider,
    FakeWebSearchProvider,
)
from app.research.models import MapSearchRequest, ResearchBudget, WebSearchRequest
from app.research.planner import (
    SearchPlanner,
    SearchPlanValidator,
    SearchQueryGenerator,
)


def criteria(*constraints, target_count=50):
    return LeadCriteria(
        task_id="task",
        task_version=1,
        business_code="GROUP_VNET",
        region_scope=["上海松江"],
        target_count=target_count,
        hard_constraints=list(constraints),
    )


def planner():
    caps = {
        "enterprise": FakeEnterpriseProvider.capabilities,
        "map": FakeMapProvider.capabilities,
        "web_search": FakeWebSearchProvider.capabilities,
    }
    return SearchPlanner(caps, budget=ResearchBudget(max_candidates=120)), caps


def test_pushdown_candidate_target_and_enrichment_explain():
    value, caps = planner()
    plan = value.build(
        criteria(
            CompiledConstraint(field="region", operator="EQ", value="上海松江"),
            CompiledConstraint(field="industry", operator="EQ", value="制造业"),
            CompiledConstraint(field="office_count", operator="GTE", value=2),
        )
    )
    assert plan.candidate_target == 120
    assert set(plan.pushdown_explain["enterprise"]["provider_filters"]) == {
        "region",
        "industry",
    }
    assert (
        "office_count" in plan.pushdown_explain["enterprise"]["enrichment_requirements"]
    )
    SearchPlanValidator(
        set(caps), set().union(*(v.supported_fields for v in caps.values()))
    ).validate(plan)


def test_unresolvable_hard_constraint_is_rejected():
    value, caps = planner()
    plan = value.build(
        criteria(CompiledConstraint(field="credit_rating", operator="GTE", value=3))
    )
    with pytest.raises(ValueError, match="UNRESOLVABLE_HARD_CONSTRAINT"):
        SearchPlanValidator(
            set(caps), set().union(*(v.supported_fields for v in caps.values()))
        ).validate(plan)


def test_query_generator_returns_bounded_deduplicated_schema():
    result = SearchQueryGenerator(max_variants=2).generate(criteria())
    assert len(result.map_queries) <= 2 and len(result.web_queries) <= 2
    assert len(result.map_queries) == len(set(result.map_queries))


def test_provider_request_boundaries_are_schema_enforced():
    with pytest.raises(ValueError):
        MapSearchRequest(keywords="x", page=101)
    with pytest.raises(ValueError):
        WebSearchRequest(query="x", include_domains=["https://example.com/a"])
