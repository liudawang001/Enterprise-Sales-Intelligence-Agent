from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Role(StrEnum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class Principal(BaseModel):
    user_id: str
    workspace_id: str
    roles: set[Role] = Field(default_factory=set)

    def has_any_role(self, *roles: Role) -> bool:
        return bool(self.roles.intersection(roles))
