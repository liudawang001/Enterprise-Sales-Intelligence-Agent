import operator
from typing import Annotated, TypedDict


class VerificationState(TypedDict, total=False):
    task_id: str
    researched_candidate_set_id: str
    resolution_run_id: str | None
    canonical_enterprise_ids: list[str]
    verification_run_id: str | None
    verified_profile_ids: list[str]
    unresolved_enterprise_ids: list[str]
    conflicting_enterprise_ids: list[str]
    verification_round: int
    verification_max_rounds: int
    progress: dict
    warnings: Annotated[list[str], operator.add]
    errors: Annotated[list[dict], operator.add]
