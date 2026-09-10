from uuid import uuid4

from app.domain.rule import LeadCriteria


class MockBusinessService:
    def retrieve_context(self, business: str | None) -> dict:
        return {
            "ref": f"mock-business-{business or 'unknown'}",
            "text": "适合具有企业内部通信需求的集团客户。多个办公地点企业优先。",
        }

    def build_criteria(self, *, business: str, region: str, target_count: int) -> tuple[str, LeadCriteria]:
        criteria = LeadCriteria(
            business=business,
            hard_constraints=[{"field": "region", "operator": "=", "value": region, "source": "USER_REQUIREMENT"}],
            soft_constraints=[{"field": "office_count", "operator": ">=", "value": 2, "source": "MARKETING_RULE"}],
            required_fields=["company_name", "phone", "address"],
            ranking_preferences=[{"field": "score", "direction": "desc"}],
        )
        return str(uuid4()), criteria
