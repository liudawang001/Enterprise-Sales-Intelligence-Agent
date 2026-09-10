from copy import deepcopy
from uuid import uuid4

from app.domain.task import Lead


MOCK_LEADS = [
    Lead(company_name="上海华东智造有限公司", industry="制造业", region="上海松江", phone="021-55550001", address="上海市松江区新桥镇", office_count=3),
    Lead(company_name="松江现代物流有限公司", industry="物流", region="上海松江", phone="021-55550002", address="上海市松江区九亭镇", office_count=2),
    Lead(company_name="上海云创科技有限公司", industry="科技", region="上海松江", phone="021-55550003", address="上海市松江区广富林路", office_count=2),
    Lead(company_name="东华工业设备有限公司", industry="制造业", region="上海松江", phone="021-55550004", address="上海市松江区车墩镇", office_count=1),
    Lead(company_name="上海新联供应链有限公司", industry="物流", region="上海松江", phone="021-55550005", address="上海市松江区洞泾镇", office_count=2),
]


class MockResearchService:
    def __init__(self) -> None:
        self._candidate_sets: dict[str, list[Lead]] = {}

    def build_search_plan(self, target_count: int) -> str:
        return str(uuid4())

    def discover(self, *, region: str) -> tuple[str, list[Lead]]:
        leads = [lead for lead in deepcopy(MOCK_LEADS) if lead.region == region]
        if not leads:
            leads = deepcopy(MOCK_LEADS)
            for lead in leads:
                lead.region = region
        candidate_set_id = str(uuid4())
        self._candidate_sets[candidate_set_id] = deepcopy(leads)
        return candidate_set_id, leads

    def get_candidates(self, candidate_set_id: str | None) -> list[Lead]:
        if not candidate_set_id:
            return []
        return deepcopy(self._candidate_sets.get(candidate_set_id, []))

    def enrich_and_verify(self, leads: list[Lead]) -> tuple[str, list[Lead]]:
        return str(uuid4()), leads
