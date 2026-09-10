from pydantic import BaseModel, Field


class LeadCriteria(BaseModel):
    business: str
    hard_constraints: list[dict] = Field(default_factory=list)
    soft_constraints: list[dict] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    ranking_preferences: list[dict] = Field(default_factory=list)
