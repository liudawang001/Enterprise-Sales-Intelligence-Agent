from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import uuid4

from app.config import Settings, get_settings
from app.criteria.evaluator import DefaultCriteriaEvaluator
from app.criteria.models import LeadCriteria
from app.domain.task import Lead
from app.providers.factory import ProviderFactory, ResearchProviders
from app.research.models import (
    CandidateSet,
    CandidateStatus,
    CompanyWebFacts,
    EnterpriseProfileRequest,
    EnterpriseSearchRequest,
    FilterOutcome,
    MapSearchRequest,
    ProviderQuery,
    RawEnterpriseCandidate,
    ResearchBudget,
    ResearchRun,
    ResearchRunStatus,
    ResearchSourceType,
    SourceRecord,
    ToolStatus,
    WebFetchRequest,
    WebSearchRequest,
    WebsiteCandidate,
)
from app.research.planner import SearchPlanner, SearchPlanValidator
from app.research.region import RegionResolver
from app.research.repository import InMemoryResearchRepository
from app.research.runtime import BoundedProviderRuntime, BudgetGuard
from app.research.safety import filter_public_contacts


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip().lower()
    return re.sub(r"\s+", "", value).replace("（", "(").replace("）", ")")


def _rows(data: object) -> list[dict]:
    if isinstance(data, list):
        return [v for v in data if isinstance(v, dict)]
    if isinstance(data, dict):
        for key in ("companies", "results", "data", "items"):
            if isinstance(data.get(key), list):
                return [v for v in data[key] if isinstance(v, dict)]
    return []


class WebsiteDiscoveryService:
    @staticmethod
    def choose(company_name: str, rows: list[dict]) -> WebsiteCandidate | None:
        token = normalize_name(company_name).replace("有限公司", "")
        scored = []
        for index, row in enumerate(rows):
            if not row.get("url"):
                continue
            signals = []
            if token and token in normalize_name(str(row.get("title", ""))):
                signals.append("COMPANY_NAME_IN_TITLE")
            confidence = min(1.0, float(row.get("score", 0)) + (0.3 if signals else 0))
            candidate = WebsiteCandidate(
                url=row["url"],
                domain=urlparse(str(row["url"])).hostname or "",
                title=row.get("title"),
                source_provider=str(row.get("provider", "web_search")),
                search_rank=index + 1,
                matching_signals=signals,
                provisional_confidence=confidence,
            )
            scored.append((confidence, -index, candidate))
        return max(scored, key=lambda item: (item[0], item[1]))[2] if scored else None


def select_internal_links(home_url: str, content: str, max_pages: int) -> list[str]:
    keywords = (
        "contact",
        "about",
        "location",
        "office",
        "branch",
        "联系我们",
        "关于我们",
        "分支机构",
        "办公地点",
        "公司简介",
    )
    home_domain = urlparse(home_url).hostname
    links = re.findall(r"\[[^]]*\]\((https?://[^)\s]+)\)", content)
    selected = [
        url
        for url in links
        if urlparse(url).hostname == home_domain
        and any(keyword in url.lower() for keyword in keywords)
    ]
    return list(dict.fromkeys(selected))[: max(0, max_pages - 1)]


class WebFactExtractor:
    """Deterministic baseline: external instructions are treated only as text."""

    @staticmethod
    def extract(text: str, domain: str | None = None) -> CompanyWebFacts:
        phones, emails = filter_public_contacts(text[:30000])
        return CompanyWebFacts(
            public_phones=phones, public_emails=emails, website_domain=domain
        )


class ResearchService:
    def __init__(
        self,
        providers: ResearchProviders | None = None,
        repository: InMemoryResearchRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.providers = providers or ProviderFactory.build(self.settings)
        self.repository = repository or InMemoryResearchRepository()
        self.region_resolver = RegionResolver()
        self._runtimes: dict[str, BoundedProviderRuntime] = {}
        self._legacy_sets: dict[str, list[Lead]] = {}

    def _budget(self) -> ResearchBudget:
        return ResearchBudget(
            max_tool_calls=self.settings.research_max_tool_calls,
            max_web_search_calls=self.settings.research_max_web_searches,
            max_web_fetch_calls=self.settings.research_max_web_pages,
            max_web_pages=self.settings.research_max_web_pages,
            max_candidates=self.settings.research_max_candidates,
        )

    def build_plan(self, criteria: LeadCriteria) -> tuple[ResearchRun, object]:
        caps = {
            "enterprise": self.providers.enterprise.capabilities,
            "map": self.providers.map.capabilities,
            "web_search": self.providers.web_search.capabilities,
        }
        plan = SearchPlanner(
            caps,
            discovery_multiplier=self.settings.research_discovery_multiplier,
            max_candidates=self.settings.research_max_candidates,
            batch_size=self.settings.research_batch_size,
            max_expansion_rounds=self.settings.research_max_expansion_rounds,
            budget=self._budget(),
        ).build(criteria)
        SearchPlanValidator(
            set(caps), set().union(*(v.supported_fields for v in caps.values()))
        ).validate(plan)
        run = ResearchRun(
            task_id=criteria.task_id,
            criteria_snapshot_id=criteria.criteria_id,
            search_plan_id=plan.plan_id,
            status=ResearchRunStatus.RUNNING,
            stage="SEARCH_PLAN_CREATED",
            budget=plan.budget,
        )
        self.repository.save_plan(plan)
        self.repository.save_run(run)
        self.repository.record_event(
            run.research_run_id,
            "RESEARCH_PLAN_CREATED",
            search_plan_id=plan.plan_id,
            candidate_target=plan.candidate_target,
        )
        limits = {
            "enterprise_search": self.settings.research_enterprise_concurrency,
            "enterprise_profile": self.settings.research_enterprise_concurrency,
            "map": self.settings.research_map_concurrency,
            "web_search": self.settings.research_web_search_concurrency,
            "web_fetch": self.settings.research_web_fetch_concurrency,
        }
        self._runtimes[run.research_run_id] = BoundedProviderRuntime(
            self.repository,
            BudgetGuard(plan.budget),
            max_retries=self.settings.research_max_retries,
            concurrency=limits,
        )
        return run, plan

    async def run_discovery_batch(self, run_id: str, queries: list[dict]) -> str:
        run = self.repository.runs[run_id]
        candidate_ids = []
        for raw in queries:
            query = ProviderQuery.model_validate(raw)
            if query.provider_type == "enterprise":
                request = EnterpriseSearchRequest(
                    query=query.query_text,
                    filters=query.filters,
                    region=query.region,
                    page=query.page or 1,
                    page_size=query.page_size or 20,
                )
                result = await self._runtimes[run_id].execute(
                    research_run_id=run_id,
                    task_id=run.task_id,
                    query_id=query.query_id,
                    provider=self.providers.enterprise.name,
                    operation="enterprise_search",
                    arguments=request.model_dump(),
                    call=lambda r=request: self.providers.enterprise.search_companies(
                        r
                    ),
                )
                source_type = ResearchSourceType.ENTERPRISE_DATABASE
            elif query.provider_type == "map":
                region = self.region_resolver.resolve(query.region or "")
                request = MapSearchRequest(
                    keywords=query.query_text or "企业",
                    region=region.name,
                    adcode=region.adcode,
                    page=query.page or 1,
                    page_size=min(query.page_size or 20, 25),
                )
                result = await self._runtimes[run_id].execute(
                    research_run_id=run_id,
                    task_id=run.task_id,
                    query_id=query.query_id,
                    provider=self.providers.map.name,
                    operation="map",
                    arguments=request.model_dump(),
                    call=lambda r=request: self.providers.map.search_places(r),
                )
                source_type = ResearchSourceType.MAP_POI
            else:
                request = WebSearchRequest(
                    query=query.query_text or "企业",
                    max_results=min(query.page_size or 10, 20),
                )
                result = await self._runtimes[run_id].execute(
                    research_run_id=run_id,
                    task_id=run.task_id,
                    query_id=query.query_id,
                    provider=self.providers.web_search.name,
                    operation="web_search",
                    arguments=request.model_dump(),
                    call=lambda r=request: self.providers.web_search.search(r),
                )
                source_type = ResearchSourceType.WEB_SEARCH
            if result.status not in {ToolStatus.SUCCESS, ToolStatus.EMPTY}:
                continue
            for row in _rows(result.data):
                name = str(
                    row.get("name") or row.get("company_name") or row.get("title") or ""
                ).strip()
                if not name:
                    continue
                item = RawEnterpriseCandidate(
                    research_run_id=run_id,
                    source_provider=result.provider,
                    source_entity_id=str(row.get("id")) if row.get("id") else None,
                    source_name=name,
                    normalized_name=normalize_name(name),
                    source_url=row.get("url") or row.get("website"),
                    region=row.get("region") or query.region,
                    industry=row.get("industry"),
                    company_status=row.get("company_status"),
                    basic_scale=row.get("company_scale") or row.get("basic_scale"),
                    address=row.get("address"),
                    public_phone=row.get("public_phone") or row.get("phone"),
                    website_candidate=row.get("website") or row.get("url"),
                    office_count=row.get("office_count"),
                    employee_count=row.get("employee_count"),
                    member_count=row.get("member_count"),
                    branch_count=row.get("branch_count"),
                    locations=row.get("locations", []),
                    cross_region_presence=bool(row.get("cross_region_presence", False)),
                )
                self.repository.save_candidate(item)
                payload = (
                    row
                    if source_type != ResearchSourceType.ENTERPRISE_DATABASE
                    or result.provider.startswith("fake")
                    else None
                )
                self.repository.save_source(
                    SourceRecord(
                        research_run_id=run_id,
                        candidate_id=item.candidate_id,
                        provider=result.provider,
                        source_type=source_type,
                        source_id=item.source_entity_id,
                        source_url=item.source_url,
                        payload_json=payload,
                        http_status=200,
                    )
                )
                candidate_ids.append(item.candidate_id)
        return self.repository.save_batch_result(
            str(uuid4()),
            candidate_ids,
            research_run_id=run_id,
            stage="DISCOVERY",
            query_ids=[ProviderQuery.model_validate(v).query_id for v in queries],
        )

    def merge_discovery(self, run_id: str, refs: list[str]) -> CandidateSet:
        provider_ids: dict[tuple[str, str], str] = {}
        names_and_addresses: dict[tuple[str, str], str] = {}
        urls: dict[str, str] = {}
        selected = []
        for ref in refs:
            for cid in self.repository.batch_results.get(ref, []):
                item = self.repository.candidates[cid]
                if item.research_run_id != run_id:
                    continue
                duplicate_id = (
                    provider_ids.get((item.source_provider, item.source_entity_id))
                    if item.source_entity_id
                    else None
                )
                if not duplicate_id and item.address:
                    duplicate_id = names_and_addresses.get(
                        (item.normalized_name, item.address)
                    )
                if not duplicate_id and item.source_url:
                    duplicate_id = urls.get(item.source_url)
                if duplicate_id:
                    for source in self.repository.get_sources(cid):
                        self.repository.save_source(
                            source.model_copy(
                                update={
                                    "source_record_id": str(uuid4()),
                                    "candidate_id": duplicate_id,
                                }
                            )
                        )
                    continue
                selected.append(cid)
                if item.source_entity_id:
                    provider_ids[(item.source_provider, item.source_entity_id)] = cid
                if item.address:
                    names_and_addresses[(item.normalized_name, item.address)] = cid
                if item.source_url:
                    urls[item.source_url] = cid
        discovery_runs = [
            value
            for value in self.repository.tool_runs.values()
            if value.research_run_id == run_id
            and value.tool_name in {"enterprise_search", "map", "web_search"}
        ]
        if (
            not selected
            and discovery_runs
            and all(value.status == ToolStatus.FAILED for value in discovery_runs)
        ):
            self.repository.runs[run_id] = self.repository.runs[run_id].model_copy(
                update={
                    "status": ResearchRunStatus.FAILED,
                    "error_code": "ALL_DISCOVERY_PROVIDERS_UNAVAILABLE",
                }
            )
            raise RuntimeError("ALL_DISCOVERY_PROVIDERS_UNAVAILABLE")
        plan = self.repository.plans[self.repository.runs[run_id].search_plan_id]
        result = self.repository.save_candidate_set(
            CandidateSet(
                research_run_id=run_id,
                stage="RAW",
                criteria_snapshot_id=plan.criteria_snapshot_id,
                search_plan_id=plan.plan_id,
                candidate_ids=selected[: plan.budget.max_candidates],
            )
        )
        self.repository.runs[run_id] = self.repository.runs[run_id].model_copy(
            update={
                "raw_candidate_set_id": result.candidate_set_id,
                "stage": "DISCOVERY_COMPLETED",
            }
        )
        self.repository.record_event(
            run_id, "DISCOVERY_COMPLETED", candidate_count=result.candidate_count
        )
        return result

    async def enrich_batch(self, run_id: str, candidate_ids: list[str]) -> str:
        run = self.repository.runs[run_id]
        for cid in candidate_ids:
            item = self.repository.candidates[cid]
            if (
                item.source_entity_id
                and item.source_provider == self.providers.enterprise.name
            ):
                request = EnterpriseProfileRequest(company_id=item.source_entity_id)
                result = await self._runtimes[run_id].execute(
                    research_run_id=run_id,
                    task_id=run.task_id,
                    query_id=None,
                    provider=self.providers.enterprise.name,
                    operation="enterprise_profile",
                    arguments=request.model_dump(),
                    call=lambda r=request: (
                        self.providers.enterprise.get_company_profile(r)
                    ),
                )
                if result.status == ToolStatus.SUCCESS and isinstance(
                    result.data, dict
                ):
                    updates = {
                        key: result.data[key]
                        for key in (
                            "industry",
                            "company_status",
                            "employee_count",
                            "member_count",
                            "office_count",
                            "address",
                            "public_phone",
                            "locations",
                        )
                        if result.data.get(key) is not None
                    }
                    item = item.model_copy(
                        update={**updates, "status": CandidateStatus.ENRICHED}
                    )
                    self.repository.save_candidate(item)
            if item.office_count is None:
                region = self.region_resolver.resolve(item.region or "")
                request = MapSearchRequest(
                    keywords=item.source_name, region=region.name, adcode=region.adcode
                )
                result = await self._runtimes[run_id].execute(
                    research_run_id=run_id,
                    task_id=run.task_id,
                    query_id=None,
                    provider=self.providers.map.name,
                    operation="map",
                    arguments=request.model_dump(),
                    call=lambda r=request: self.providers.map.search_places(r),
                )
                if result.status == ToolStatus.SUCCESS:
                    places = _rows(result.data)
                    item = item.model_copy(
                        update={
                            "office_count": len(places),
                            "locations": [
                                p.get("address") for p in places if p.get("address")
                            ],
                            "status": CandidateStatus.ENRICHED,
                        }
                    )
                    self.repository.save_candidate(item)
                    for place in places:
                        self.repository.save_source(
                            SourceRecord(
                                research_run_id=run_id,
                                candidate_id=cid,
                                provider=self.providers.map.name,
                                source_type=ResearchSourceType.MAP_POI,
                                source_id=place.get("id"),
                                payload_json=place,
                                http_status=200,
                            )
                        )
        return self.repository.save_batch_result(
            str(uuid4()),
            candidate_ids,
            research_run_id=run_id,
            stage="CHEAP_ENRICHMENT",
        )

    def persist_cheap_enriched_set(
        self, run_id: str, parent_set_id: str
    ) -> CandidateSet:
        run, plan = (
            self.repository.runs[run_id],
            self.repository.plans[self.repository.runs[run_id].search_plan_id],
        )
        ids = [
            item.candidate_id for item in self.repository.get_candidates(parent_set_id)
        ]
        result = self.repository.save_candidate_set(
            CandidateSet(
                research_run_id=run_id,
                parent_set_id=parent_set_id,
                stage="CHEAP_ENRICHED",
                criteria_snapshot_id=plan.criteria_snapshot_id,
                search_plan_id=plan.plan_id,
                candidate_ids=ids,
            )
        )
        self.repository.runs[run_id] = run.model_copy(
            update={
                "cheap_enriched_set_id": result.candidate_set_id,
                "stage": "ENRICHMENT_COMPLETED",
            }
        )
        self.repository.record_event(
            run_id, "ENRICHMENT_COMPLETED", candidate_count=result.candidate_count
        )
        return result

    def apply_hard_filters(
        self, run_id: str, parent_set_id: str, criteria: LeadCriteria
    ) -> CandidateSet:
        selected = []
        evaluator = DefaultCriteriaEvaluator()
        for item in self.repository.get_candidates(parent_set_id):
            outcome = evaluator.evaluate_hard_constraints(item.model_dump(), criteria)
            if outcome == FilterOutcome.NO_MATCH:
                self.repository.save_candidate(
                    item.model_copy(update={"status": CandidateStatus.FILTERED_OUT})
                )
            else:
                selected.append(item.candidate_id)
        plan = self.repository.plans[self.repository.runs[run_id].search_plan_id]
        result = self.repository.save_candidate_set(
            CandidateSet(
                research_run_id=run_id,
                parent_set_id=parent_set_id,
                stage="FILTERED",
                criteria_snapshot_id=criteria.criteria_id,
                search_plan_id=plan.plan_id,
                candidate_ids=selected,
            )
        )
        self.repository.runs[run_id] = self.repository.runs[run_id].model_copy(
            update={
                "filtered_candidate_set_id": result.candidate_set_id,
                "stage": "FILTER_COMPLETED",
            }
        )
        self.repository.record_event(
            run_id, "FILTER_COMPLETED", candidate_count=result.candidate_count
        )
        return result

    async def deep_research_batch(self, run_id: str, candidate_ids: list[str]) -> str:
        run = self.repository.runs[run_id]
        for cid in candidate_ids:
            item = self.repository.candidates[cid]
            website = item.website_candidate
            if not website:
                request = WebSearchRequest(
                    query=f'"{item.source_name}" 官网', max_results=5
                )
                result = await self._runtimes[run_id].execute(
                    research_run_id=run_id,
                    task_id=run.task_id,
                    query_id=None,
                    provider=self.providers.web_search.name,
                    operation="web_search",
                    arguments=request.model_dump(),
                    call=lambda r=request: self.providers.web_search.search(r),
                )
                rows = _rows(result.data) if result.status == ToolStatus.SUCCESS else []
                website_candidate = WebsiteDiscoveryService.choose(
                    item.source_name, rows
                )
                website = str(website_candidate.url) if website_candidate else None
                for row in rows:
                    self.repository.save_source(
                        SourceRecord(
                            research_run_id=run_id,
                            candidate_id=cid,
                            provider=self.providers.web_search.name,
                            source_type=ResearchSourceType.WEBSITE_CANDIDATE,
                            source_url=row.get("url"),
                            payload_json={
                                "title": row.get("title"),
                                "score": row.get("score"),
                            },
                            http_status=200,
                        )
                    )
            if not website:
                self.repository.save_candidate(
                    item.model_copy(update={"status": CandidateStatus.PARTIAL})
                )
                continue
            try:
                request = WebFetchRequest(url=website)
            except ValueError:
                self.repository.save_candidate(
                    item.model_copy(update={"status": CandidateStatus.PARTIAL})
                )
                continue
            result = await self._runtimes[run_id].execute(
                research_run_id=run_id,
                task_id=run.task_id,
                query_id=None,
                provider=self.providers.web_fetch.name,
                operation="web_fetch",
                arguments=request.model_dump(mode="json"),
                call=lambda r=request: self.providers.web_fetch.fetch(r),
            )
            if result.status == ToolStatus.SUCCESS:
                text = str((result.data or {}).get("markdown", ""))[:30000]
                page_texts = [text]
                for internal_url in select_internal_links(
                    website, text, self.settings.research_max_pages_per_company
                ):
                    internal_request = WebFetchRequest(url=internal_url)
                    internal_result = await self._runtimes[run_id].execute(
                        research_run_id=run_id,
                        task_id=run.task_id,
                        query_id=None,
                        provider=self.providers.web_fetch.name,
                        operation="web_fetch",
                        arguments=internal_request.model_dump(mode="json"),
                        call=lambda r=internal_request: self.providers.web_fetch.fetch(
                            r
                        ),
                    )
                    if internal_result.status == ToolStatus.SUCCESS:
                        internal_text = str(
                            (internal_result.data or {}).get("markdown", "")
                        )[:30000]
                        page_texts.append(internal_text)
                        self.repository.save_source(
                            SourceRecord(
                                research_run_id=run_id,
                                candidate_id=cid,
                                provider=self.providers.web_fetch.name,
                                source_type=ResearchSourceType.PUBLIC_WEBPAGE,
                                source_url=internal_url,
                                content_text=internal_text,
                                content_hash=hashlib.sha256(
                                    internal_text.encode()
                                ).hexdigest(),
                                http_status=200,
                            )
                        )
                facts = WebFactExtractor.extract(
                    "\n".join(page_texts), urlparse(website).hostname
                )
                update = {
                    "website_candidate": website,
                    "status": CandidateStatus.RESEARCHED,
                }
                if facts.public_phones and not item.public_phone:
                    update["public_phone"] = facts.public_phones[0]
                self.repository.save_candidate(item.model_copy(update=update))
                self.repository.save_source(
                    SourceRecord(
                        research_run_id=run_id,
                        candidate_id=cid,
                        provider=self.providers.web_fetch.name,
                        source_type=ResearchSourceType.PUBLIC_WEBPAGE,
                        source_url=website,
                        content_text=text,
                        content_hash=hashlib.sha256(text.encode()).hexdigest(),
                        http_status=200,
                    )
                )
            else:
                self.repository.save_candidate(
                    item.model_copy(update={"status": CandidateStatus.PARTIAL})
                )
        return self.repository.save_batch_result(
            str(uuid4()), candidate_ids, research_run_id=run_id, stage="DEEP_RESEARCH"
        )

    def finalize(
        self, run_id: str, parent_set_id: str, candidate_ids: list[str]
    ) -> CandidateSet:
        run, plan = (
            self.repository.runs[run_id],
            self.repository.plans[self.repository.runs[run_id].search_plan_id],
        )
        result = self.repository.save_candidate_set(
            CandidateSet(
                research_run_id=run_id,
                parent_set_id=parent_set_id,
                stage="RESEARCHED",
                criteria_snapshot_id=plan.criteria_snapshot_id,
                search_plan_id=plan.plan_id,
                candidate_ids=candidate_ids[: plan.target_count],
            )
        )
        exhausted = any(
            value.research_run_id == run_id
            and value.status == ToolStatus.BUDGET_BLOCKED
            for value in self.repository.tool_runs.values()
        )
        status = (
            ResearchRunStatus.COMPLETED
            if result.candidate_count >= plan.target_count and not exhausted
            else ResearchRunStatus.PARTIAL
        )
        error_code = (
            "BUDGET_EXHAUSTED"
            if exhausted
            else None
            if status == ResearchRunStatus.COMPLETED
            else "INSUFFICIENT_CANDIDATES"
        )
        self.repository.runs[run_id] = run.model_copy(
            update={
                "researched_candidate_set_id": result.candidate_set_id,
                "status": status,
                "stage": "RESEARCH_COMPLETED",
                "used_budget": dict(self._runtimes[run_id].guard.used),
                "error_code": error_code,
                "finished_at": datetime.now(UTC),
            }
        )
        self.repository.record_event(
            run_id,
            "RESEARCH_COMPLETED",
            status=status.value,
            candidate_count=result.candidate_count,
            error_code=error_code,
        )
        return result

    def get_candidates(self, candidate_set_id: str | None) -> list[Lead]:
        if candidate_set_id in self._legacy_sets:
            return [
                item.model_copy(deep=True)
                for item in self._legacy_sets[candidate_set_id]
            ]
        return [
            Lead(
                company_name=v.source_name,
                industry=v.industry,
                region=v.region,
                phone=v.public_phone,
                address=v.address,
                office_count=v.office_count,
                employee_count=v.employee_count,
                member_count=v.member_count,
                branch_count=v.branch_count,
                locations=v.locations,
                company_scale=v.basic_scale,
                company_status=v.company_status,
                cross_region_presence=v.cross_region_presence,
            )
            for v in self.repository.get_candidates(candidate_set_id)
        ]

    def discover(
        self, *, region: str, criteria: LeadCriteria | None = None
    ) -> tuple[str, list[Lead]]:
        rows = getattr(self.providers.enterprise, "rows", [])
        leads = [
            Lead(
                company_name=r["name"],
                industry=r.get("industry"),
                region=region,
                phone=r.get("public_phone"),
                address=r.get("address"),
                office_count=r.get("office_count"),
                employee_count=r.get("employee_count"),
                locations=r.get("locations", []),
                company_scale=r.get("company_scale"),
                company_status=r.get("company_status"),
                cross_region_presence=r.get("cross_region_presence", False),
            )
            for r in rows
        ]
        if criteria:
            evaluator = DefaultCriteriaEvaluator()
            leads = [
                v
                for v in leads
                if evaluator.matches_hard_constraints(v.model_dump(), criteria)
            ]
        set_id = str(uuid4())
        self._legacy_sets[set_id] = [item.model_copy(deep=True) for item in leads[:5]]
        return set_id, leads[:5]


MockResearchService = ResearchService
