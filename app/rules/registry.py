from __future__ import annotations

from pydantic import BaseModel

from app.rules.models import RuleOperator


class RuleFieldDefinition(BaseModel):
    name: str
    value_type: str
    allowed_operators: list[RuleOperator]
    searchable: bool = True
    rankable: bool = True
    description: str = ""


class RuleFieldRegistry:
    def __init__(self) -> None:
        numeric = [RuleOperator.EQ, RuleOperator.NE, RuleOperator.GT, RuleOperator.GTE, RuleOperator.LT, RuleOperator.LTE]
        self._fields = {
            "region": RuleFieldDefinition(name="region", value_type="STRING", allowed_operators=[RuleOperator.EQ, RuleOperator.NE, RuleOperator.CONTAINS]),
            "industry": RuleFieldDefinition(name="industry", value_type="STRING", allowed_operators=[RuleOperator.EQ, RuleOperator.NE, RuleOperator.IN, RuleOperator.NOT_IN]),
            "employee_count": RuleFieldDefinition(name="employee_count", value_type="INTEGER", allowed_operators=numeric),
            "member_count": RuleFieldDefinition(name="member_count", value_type="INTEGER", allowed_operators=numeric),
            "office_count": RuleFieldDefinition(name="office_count", value_type="INTEGER", allowed_operators=numeric),
            "has_office_in": RuleFieldDefinition(name="has_office_in", value_type="STRING", allowed_operators=[RuleOperator.EQ, RuleOperator.CONTAINS]),
            "branch_count": RuleFieldDefinition(name="branch_count", value_type="INTEGER", allowed_operators=numeric),
            "company_scale": RuleFieldDefinition(name="company_scale", value_type="ENUM", allowed_operators=[RuleOperator.EQ, RuleOperator.IN, RuleOperator.NOT_IN]),
            "company_status": RuleFieldDefinition(name="company_status", value_type="STRING", allowed_operators=[RuleOperator.EQ, RuleOperator.IN, RuleOperator.NOT_IN]),
            "existing_products": RuleFieldDefinition(name="existing_products", value_type="LIST", allowed_operators=[RuleOperator.CONTAINS, RuleOperator.IN, RuleOperator.NOT_IN]),
            "contact_availability": RuleFieldDefinition(name="contact_availability", value_type="BOOLEAN", allowed_operators=[RuleOperator.EQ]),
            "cross_region_presence": RuleFieldDefinition(name="cross_region_presence", value_type="BOOLEAN", allowed_operators=[RuleOperator.EQ]),
        }

    def get(self, name: str) -> RuleFieldDefinition | None:
        return self._fields.get(name)

    def exists(self, name: str) -> bool:
        return name in self._fields

    def all(self) -> list[RuleFieldDefinition]:
        return list(self._fields.values())


BUSINESS_CATALOG = {
    "GROUP_VNET": {"code": "GROUP_VNET", "name": "集团V网", "aliases": ["集团 V 网", "V网", "集团V网业务"], "enabled": True},
    "ENTERPRISE_DEDICATED_LINE": {"code": "ENTERPRISE_DEDICATED_LINE", "name": "企业专线", "aliases": ["专线", "企业专线业务"], "enabled": True},
}


def normalize_business_code(value: str) -> str:
    text = value.strip()
    for code, definition in BUSINESS_CATALOG.items():
        if text == code or text == definition["name"] or text in definition["aliases"]:
            return code
    return text

