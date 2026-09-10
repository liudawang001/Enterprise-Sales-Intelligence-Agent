import re
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.types import interrupt

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState
from app.domain.task import ConstraintPatch, TaskPatch


REQUIRED_SLOTS = ("business", "region", "target_count")


def _extract_region(text: str) -> str | None:
    for pattern in (r"(上海松江)", r"(上海浦东)", r"(上海[\u4e00-\u9fff]{1,6})"):
        match = re.search(pattern, text)
        if match:
            return match.group(1)
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
