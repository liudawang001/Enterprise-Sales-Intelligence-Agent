from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.criteria.models import CompiledConstraint, LeadCriteria
from app.research.models import (
    ProviderCapabilities,
    ProviderQuery,
    QueryPurpose,
    ResearchBudget,
    SearchPlan,
)


@dataclass
class PushdownResult:
    provider_filters: dict[str, object]
    post_filters: list[CompiledConstraint]
    enrichment_requirements: list[str]


class SearchQueryVariants(BaseModel):
    map_queries: list[str] = Field(default_factory=list)
    web_queries: list[str] = Field(default_factory=list)


class SearchQueryGenerator:
    """Bounded structured query generation with a deterministic offline path."""

    def __init__(self, max_variants: int = 4) -> None:
        self.max_variants = max_variants

    def generate(self, criteria: LeadCriteria) -> SearchQueryVariants:
        region = criteria.region_scope[0] if criteria.region_scope else ""
        industries = [
            str(item.value)
            for item in criteria.hard_constraints + criteria.soft_constraints
            if item.field == "industry"
        ]
        industry = industries[0] if industries else "企业"
        map_queries = [f"{region} {industry} 公司", f"{region} {industry} 企业"]
        web_subject = industry if industry != "企业" else "公司"
        web_queries = [
            f"{region} {web_subject} 官网",
            f"{region} {criteria.business_code} 企业名录",
        ]
        dedupe = lambda values: list(
            dict.fromkeys(value.strip() for value in values if value.strip())
        )[: self.max_variants]
        return SearchQueryVariants(
            map_queries=dedupe(map_queries), web_queries=dedupe(web_queries)
        )

    async def generate_with_llm(
        self, criteria: LeadCriteria, llm: object
    ) -> SearchQueryVariants:
        structured = llm.with_structured_output(SearchQueryVariants)
        prompt = (
            "Generate only bounded map_queries and web_queries for enterprise discovery. "
            "Do not generate company facts or relax hard constraints.\n"
            f"Criteria: {criteria.model_dump_json(exclude={'source_rule_ids'})}"
        )
        result = await structured.ainvoke(prompt)
        validated = SearchQueryVariants.model_validate(result)
        return SearchQueryVariants(
            map_queries=list(dict.fromkeys(validated.map_queries))[: self.max_variants],
            web_queries=list(dict.fromkeys(validated.web_queries))[: self.max_variants],
        )


class CriteriaPushdownPlanner:
    def plan(
        self,
        constraints: Iterable[CompiledConstraint],
        capabilities: ProviderCapabilities,
    ) -> PushdownResult:
        pushed, post, enrichment = {}, [], []
        for item in constraints:
            if capabilities.supports(item.field, item.operator.value):
                pushed[item.field] = {
                    "operator": item.operator.value,
                    "value": item.value,
                }
            else:
                post.append(item)
                enrichment.append(item.field)
        return PushdownResult(pushed, post, list(dict.fromkeys(enrichment)))


class SearchPlanner:
    def __init__(
        self,
        capabilities: dict[str, ProviderCapabilities],
        *,
        discovery_multiplier: int = 4,
        max_candidates: int = 300,
        batch_size: int = 10,
        max_query_variants: int = 4,
        max_expansion_rounds: int = 2,
        budget: ResearchBudget | None = None,
    ) -> None:
        self.capabilities, self.discovery_multiplier = (
            capabilities,
            discovery_multiplier,
        )
        self.batch_size, self.max_query_variants, self.max_expansion_rounds = (
            batch_size,
            max_query_variants,
            max_expansion_rounds,
        )
        self.budget = budget or ResearchBudget(max_candidates=max_candidates)
        self.max_candidates = min(max_candidates, self.budget.max_candidates)

    def build(self, criteria: LeadCriteria) -> SearchPlan:
        region = criteria.region_scope[0] if criteria.region_scope else None
        pushdowns: dict[str, dict] = {}
        all_post: dict[str, CompiledConstraint] = {}
        queries: list[ProviderQuery] = []
        for provider_type in ("enterprise", "map", "web_search"):
            capability = self.capabilities[provider_type]
            result = CriteriaPushdownPlanner().plan(
                criteria.hard_constraints, capability
            )
            pushdowns[provider_type] = {
                "provider_filters": result.provider_filters,
                "post_filters": [
                    item.model_dump(mode="json") for item in result.post_filters
                ],
                "enrichment_requirements": result.enrichment_requirements,
            }
            all_post.update({item.field: item for item in result.post_filters})
        enterprise_filters = pushdowns["enterprise"]["provider_filters"]
        queries.append(
            ProviderQuery(
                provider_type="enterprise",
                filters=enterprise_filters,
                region=region,
                page_size=min(100, self.max_candidates),
                priority=100,
            )
        )
        variants = SearchQueryGenerator(self.max_query_variants).generate(criteria)
        if variants.map_queries:
            queries.append(
                ProviderQuery(
                    provider_type="map",
                    purpose=QueryPurpose.LOCATION_DISCOVERY,
                    query_text=variants.map_queries[0],
                    region=region,
                    page_size=20,
                    priority=60,
                )
            )
        if variants.web_queries:
            queries.append(
                ProviderQuery(
                    provider_type="web_search",
                    query_text=variants.web_queries[0],
                    region=region,
                    page_size=min(20, self.max_query_variants * 5),
                    priority=40,
                )
            )
        required = list(
            dict.fromkeys(
                criteria.required_fields
                + [item.field for item in criteria.hard_constraints]
            )
        )
        cheap = [
            f
            for f in required
            if f
            in {
                "region",
                "industry",
                "company_status",
                "employee_count",
                "company_scale",
                "address",
                "office_count",
            }
        ]
        deep = [f for f in required if f not in cheap]
        if set(required) & {
            "phone",
            "public_phone",
            "address",
            "website",
            "office_count",
            "locations",
        }:
            deep.append("website")
        if set(required) & {"office_count", "locations"}:
            deep.append("office_locations")
        return SearchPlan(
            task_id=criteria.task_id,
            criteria_snapshot_id=criteria.criteria_id,
            target_count=criteria.target_count,
            candidate_target=min(
                criteria.target_count * self.discovery_multiplier, self.max_candidates
            ),
            discovery_queries=queries[: self.max_query_variants],
            cheap_enrichment_fields=list(dict.fromkeys(cheap)),
            deep_research_fields=list(dict.fromkeys(deep)),
            post_filter_fields=list(all_post),
            pushdown_explain=pushdowns,
            budget=self.budget,
            batch_size=self.batch_size,
            max_expansion_rounds=self.max_expansion_rounds,
        )


class SearchPlanValidator:
    def __init__(self, provider_names: set[str], allowed_fields: set[str]) -> None:
        self.provider_names, self.allowed_fields = provider_names, allowed_fields

    def validate(self, plan: SearchPlan) -> None:
        if len(plan.discovery_queries) > plan.budget.max_tool_calls:
            raise ValueError("SEARCH_PLAN_EXCEEDS_BUDGET")
        for query in plan.discovery_queries:
            if query.provider_type not in self.provider_names:
                raise ValueError(f"UNKNOWN_PROVIDER:{query.provider_type}")
            if query.page_size is None or not 1 <= query.page_size <= 100:
                raise ValueError("INVALID_PAGE_SIZE")
            unknown = set(query.filters) - self.allowed_fields
            if unknown:
                raise ValueError(f"INVALID_PROVIDER_FIELDS:{sorted(unknown)}")
        unavailable = set(plan.post_filter_fields) - self.allowed_fields
        if unavailable:
            raise ValueError(f"UNRESOLVABLE_HARD_CONSTRAINT:{sorted(unavailable)}")
        covered = set().union(
            *(
                set(v["provider_filters"]) | set(v["enrichment_requirements"])
                for v in plan.pushdown_explain.values()
            )
        )
        missing = set(plan.post_filter_fields) - covered
        if missing:
            raise ValueError(f"UNRESOLVABLE_HARD_CONSTRAINT:{sorted(missing)}")
