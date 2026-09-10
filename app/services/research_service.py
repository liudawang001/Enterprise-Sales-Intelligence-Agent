from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

from app.domain.task import Lead
from app.criteria.evaluator import DefaultCriteriaEvaluator
from app.criteria.models import LeadCriteria


MOCK_LEADS = [
    Lead(company_name="上海华东智造有限公司", industry="制造业", region="上海松江", phone="021-55550001", address="上海市松江区新桥镇", office_count=3, employee_count=260, member_count=120, branch_count=2, locations=["上海松江", "上海闵行"], company_scale="LARGE", company_status="ACTIVE", cross_region_presence=True),
    Lead(company_name="松江现代物流有限公司", industry="物流", region="上海松江", phone="021-55550002", address="上海市松江区九亭镇", office_count=2, employee_count=90, member_count=45, branch_count=1, locations=["上海松江"], company_scale="MEDIUM", company_status="ACTIVE"),
    Lead(company_name="上海云创科技有限公司", industry="科技", region="上海松江", phone="021-55550003", address="上海市松江区广富林路", office_count=2, employee_count=70, member_count=30, branch_count=1, locations=["上海松江"], company_scale="MEDIUM", company_status="ACTIVE"),
    Lead(company_name="东华工业设备有限公司", industry="制造业", region="上海松江", phone="021-55550004", address="上海市松江区车墩镇", office_count=1, employee_count=55, member_count=20, locations=["上海松江"], company_scale="MEDIUM", company_status="ACTIVE"),
    Lead(company_name="上海新联供应链有限公司", industry="物流", region="上海松江", phone="021-55550005", address="上海市松江区洞泾镇", office_count=2, employee_count=35, member_count=8, branch_count=1, locations=["上海松江"], company_scale="SMALL", company_status="ACTIVE"),
]


class MockResearchService:
    def __init__(self) -> None:
        self._candidate_sets: dict[str, list[Lead]] = {}
        dataset = Path(__file__).parents[2] / "data" / "synthetic_customers" / "customers.jsonl"
        self._synthetic_leads = [Lead.model_validate(json.loads(line)) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()] if dataset.exists() else deepcopy(MOCK_LEADS)

    def build_search_plan(self, target_count: int) -> str:
        return str(uuid4())

    def discover(self, *, region: str, criteria: LeadCriteria | None = None) -> tuple[str, list[Lead]]:
        source = self._synthetic_leads if criteria else MOCK_LEADS
        leads = [lead for lead in deepcopy(source) if lead.region == region]
        if not leads:
            leads = deepcopy(source)
            for lead in leads:
                lead.region = region
        if criteria:
            evaluator = DefaultCriteriaEvaluator()
            rows = [lead.model_dump() for lead in leads]
            filtered = [lead for lead, row in zip(leads, rows) if evaluator.matches_hard_constraints(row, criteria)]
            leads = sorted(filtered, key=lambda lead: evaluator.preference_score(lead.model_dump(), criteria), reverse=True)[:5]
        candidate_set_id = str(uuid4())
        self._candidate_sets[candidate_set_id] = deepcopy(leads)
        return candidate_set_id, leads

    def get_candidates(self, candidate_set_id: str | None) -> list[Lead]:
        if not candidate_set_id:
            return []
        return deepcopy(self._candidate_sets.get(candidate_set_id, []))

    def enrich_and_verify(self, leads: list[Lead]) -> tuple[str, list[Lead]]:
        return str(uuid4()), leads
