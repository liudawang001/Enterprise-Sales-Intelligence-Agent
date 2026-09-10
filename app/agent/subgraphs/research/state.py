import operator
from typing import Annotated, TypedDict


class ResearchState(TypedDict, total=False):
    task_id: str
    criteria_snapshot_id: str
    search_plan_id: str
    research_run_id: str
    raw_candidate_set_id: str
    filtered_candidate_set_id: str
    researched_candidate_set_id: str
    candidate_set_id: str
    candidate_count: int
    verified_set_id: str
    verified_count: int
    discovery_result_refs: Annotated[list[str], operator.add]
    enrichment_result_refs: Annotated[list[str], operator.add]
    deep_research_result_refs: Annotated[list[str], operator.add]
    progress: dict
    warnings: Annotated[list[str], operator.add]
    errors: Annotated[list[dict], operator.add]
