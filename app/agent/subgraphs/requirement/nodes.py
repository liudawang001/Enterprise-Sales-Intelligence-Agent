import re
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.types import interrupt

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState
from app.domain.task import ConstraintPatch, TaskPatch


REQUIRED_SLOTS = ("business", "region", "target_count")


def _extract_region(text: str) -> str | None:
    for pattern in (r"(上海松江)", r"(上海浦东)", r"(上海[\u4e00-\u9fff]{1,6})", r"(?<!上)(松江)", r"(?<!上)(浦东)"):
        match = re.search(pattern, text)
        if match:
            return {"松江": "上海松江", "浦东": "上海浦东"}.get(match.group(1), match.group(1))
    return None


def extract_task_patch(state: AgentState) -> dict[str, Any]:
    text = state.get("clarification_text") or state.get("incoming_text") or ""
    patch: dict[str, Any] = {}
    business_match = re.search(r"(集团V网|企业专线)", text)
    if business_match:
        patch["business"] = business_match.group(1)
    region = _extract_region(text)
    if region:
        patch["region"] = region
    count_match = re.search(r"(\d+)\s*家", text)
    if count_match:
        patch["target_count"] = int(count_match.group(1))
    mutation_match = re.search(r"(?:数量|改成|改为|目标).*?(\d+)", text)
    if mutation_match and "target_count" not in patch:
        patch["target_count"] = int(mutation_match.group(1))
    if "不限制制造业" in text:
        patch["constraints"] = [ConstraintPatch(field="industry", operation="REMOVE").model_dump()]
    if re.search(r"(?:必须|只要).*(?:松江|上海松江).*(?:办公点|办公地点)|(?:必须|只要).*办公点.*(?:松江|上海松江)", text):
        patch.setdefault("constraints", []).append(ConstraintPatch(field="has_office_in", operation="ADD", operator="CONTAINS", value="上海松江", constraint_type="HARD").model_dump())
    industry = re.search(r"(制造业|物流|科技|零售|金融)(?:行业)?\s*(优先|最好|尽量|更倾向|更好)", text)
    if industry:
        patch.setdefault("constraints", []).append(ConstraintPatch(field="industry", operation="ADD", operator="EQ", value=industry.group(1), constraint_type="SOFT").model_dump())
    industry_plain = re.search(r"找(?:一些|只找)?\s*(制造业|物流|科技|零售|金融)(?:行业)?企业", text)
    if industry_plain and not industry:
        patch.setdefault("constraints", []).append(ConstraintPatch(field="industry", operation="ADD", operator="EQ", value=industry_plain.group(1), constraint_type="HARD").model_dump())
    industry_hard = re.search(r"(?:必须|只要)(?:是)?(制造业|物流|科技|零售|金融)(?:行业)?", text)
    if industry_hard:
        patch.setdefault("constraints", []).append(ConstraintPatch(field="industry", operation="ADD", operator="EQ", value=industry_hard.group(1), constraint_type="HARD").model_dump())
    excluded = re.search(r"(?:排除|不要|不找)(制造业|物流|科技|零售|金融)", text)
    if excluded:
        patch.setdefault("constraints", []).append(ConstraintPatch(field="industry", operation="ADD", operator="NOT_IN", value=[excluded.group(1)], constraint_type="HARD").model_dump())
    if re.search(r"(?:最好|优先|尽量|更倾向).{0,8}(?:多个|多)(?:办公点|办公地点)|(?:多个|多)(?:办公点|办公地点).{0,8}(?:最好|优先|尽量|更倾向)", text):
        patch.setdefault("constraints", []).append(ConstraintPatch(field="office_count", operation="ADD", operator="GTE", value=2, constraint_type="SOFT").model_dump())
    member = re.search(r"成员(?:数|数量).*?(?:至少|不少于|>=)\s*(\d+)", text)
    if member:
        patch.setdefault("constraints", []).append(ConstraintPatch(field="member_count", operation="ADD", operator="GTE", value=int(member.group(1)), constraint_type="HARD").model_dump())
    member_lt = re.search(r"成员(?:数|数量).*?(?:少于|小于|低于|<)\s*(\d+)", text)
    if member_lt:
        patch.setdefault("constraints", []).append(ConstraintPatch(field="member_count", operation="ADD", operator="LT", value=int(member_lt.group(1)), constraint_type="HARD").model_dump())
    return {"task_patch": TaskPatch.model_validate(patch).model_dump(exclude_none=True)}


def parse_clarification(state: AgentState) -> dict[str, Any]:
    parsed = extract_task_patch(state)["task_patch"]
    original = state.get("task_patch") or {}
    merged = {**original, **parsed}
    return {"task_patch": merged}


def merge_task_patch(state: AgentState) -> dict[str, Any]:
    current = dict(state.get("task_patch") or {})
    incoming = dict(state.get("task_patch") or {})
    # The extraction node replaces task_patch; merge with the persisted task snapshot.
    deps: AgentDependencies = state["_deps"]  # type: ignore[typeddict-item]
    task = deps.task_repository.get_task(state.get("active_task_id"))
    if task:
        merged: dict[str, Any] = {
            "business": task.business,
            "region": task.region,
            "target_count": task.target_count,
            "constraints": task.constraints,
        }
        merged.update({k: v for k, v in current.items() if v is not None})
        incoming = merged
    return {"task_patch": incoming}


def validate_required_slots(state: AgentState) -> dict[str, Any]:
    patch = state.get("task_patch") or {}
    missing = [slot for slot in REQUIRED_SLOTS if patch.get(slot) in (None, "")]
    return {"missing_slots": missing}


def build_clarification(state: AgentState) -> dict[str, Any]:
    missing = state.get("missing_slots", [])
    if missing == ["region", "target_count"] or set(missing) == {"region", "target_count"}:
        question = "请确认主要筛选哪个地区，以及希望先寻找多少家企业？"
    elif missing == ["region"]:
        question = "请确认主要筛选哪个地区？"
    elif missing == ["target_count"]:
        question = "希望先寻找多少家企业？"
    else:
        question = "请补充业务、地区和目标企业数量。"
    return {"pending_question": {"text": question, "missing_slots": missing}}


def clarify_interrupt(state: AgentState) -> dict[str, Any]:
    answer = interrupt({
        "type": "CLARIFICATION_REQUIRED",
        "task_id": state.get("active_task_id"),
        "question": state.get("pending_question"),
        "missing_slots": state.get("missing_slots", []),
    })
    text = answer["text"] if isinstance(answer, dict) else str(answer)
    return {"clarification_text": text, "messages": [HumanMessage(content=text)]}


def persist_task(state: AgentState) -> dict[str, Any]:
    deps: AgentDependencies = state["_deps"]  # type: ignore[typeddict-item]
    task_id = state.get("active_task_id")
    patch = TaskPatch.model_validate(state.get("task_patch") or {})
    if task_id:
        task = deps.task_service.apply_patch(task_id, patch)
        return {
            "task_stage": task.stage.value,
            "task_status": task.status.value,
            "task_version": task.version,
        }
    return {}
