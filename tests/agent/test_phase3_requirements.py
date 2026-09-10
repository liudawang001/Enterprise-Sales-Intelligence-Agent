from app.agent.subgraphs.requirement.nodes import extract_task_patch


def _constraint(text: str, field: str) -> dict:
    constraints = extract_task_patch({"incoming_text": text})["task_patch"].get("constraints", [])
    return next(item for item in constraints if item["field"] == field)


def test_user_strength_language_maps_to_hard_and_soft():
    assert _constraint("必须在松江有办公点", "has_office_in")["constraint_type"] == "HARD"
    assert _constraint("制造业优先", "industry")["constraint_type"] == "SOFT"
    assert _constraint("最好是多个办公点的企业", "office_count")["constraint_type"] == "SOFT"
    assert _constraint("找制造业企业", "industry")["constraint_type"] == "HARD"

