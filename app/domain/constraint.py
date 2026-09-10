from typing import Any

from pydantic import BaseModel


class BusinessConstraint(BaseModel):
    field: str
    operator: str
    value: Any
    source: str = "USER_REQUIREMENT"
    constraint_type: str = "HARD"
