import operator
from typing import Annotated, TypedDict


class ResearchState(TypedDict, total=False):
    task_id: str
    criteria_snapshot_id: str
    search_plan_id: str
    candidate_set_id: str
    candidate_count: int
    verified_set_id: str
    verified_count: int
    discovery_result_refs: Annotated[list[str], operator.add]
    errors: Annotated[list[dict], operator.add]
