import pytest

from app.agent.dependencies import build_dependencies


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("不要限制制造业", {"constraints": [{"field": "industry", "operation": "REMOVE"}]}),
        ("改成30家", {"target_count": 30, "constraints": []}),
        ("最好物流企业", {"constraints": [{"field": "industry", "operation": "ADD", "operator": "EQ", "value": "物流", "constraint_type": "SOFT"}]}),
        ("必须在浦东", {"region": "上海浦东", "constraints": []}),
        ("再补官网", {"required_fields": ["company_name", "phone", "address", "website"], "constraints": []}),
    ],
)
def test_structured_mutation_parser(text, expected):
    patch = build_dependencies().task_service.parse_mutation(text)
    assert patch.model_dump(exclude_none=True) == expected
