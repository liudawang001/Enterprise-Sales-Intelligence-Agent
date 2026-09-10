from app.criteria.models import LeadCriteria
from app.rules.models import BusinessRule, ConstraintType, RuleOperator, RuleSourceType
from app.rules.service import BusinessRuleService


class MockBusinessService:
    def __init__(self, rule_service: BusinessRuleService | None = None) -> None:
        self.rule_service = rule_service or BusinessRuleService()
        self.rule_service.seed_demo_rules()

    def retrieve_context(self, business: str | None) -> dict:
        return {
            "ref": f"mock-business-{business or 'unknown'}",
            "text": "适合具有企业内部通信需求的集团客户。多个办公地点企业优先。",
        }

    def build_criteria(self, *, business: str, region: str, target_count: int) -> tuple[str, LeadCriteria]:
        rules = [
            BusinessRule(business_code=business, field="region", operator=RuleOperator.EQ, value=region, value_type="STRING", source_type=RuleSourceType.USER_REQUIREMENT, constraint_type=ConstraintType.HARD, rationale="用户指定区域", source_message_id="legacy"),
        ] + self.rule_service.repository.list_marketing(business)
        criteria = self.rule_service.compile(task_id="legacy", task_version=1, business_code=business, region=region, target_count=target_count, rules=rules)
        return criteria.criteria_id, criteria
