from __future__ import annotations

from app.rules.models import ModelSuggestion, ModelSuggestionResult
from app.rules.registry import RuleFieldRegistry


MODEL_SUGGESTION_PROMPT = """Return zero to five evidence-grounded lead ranking suggestions.
Use only fields from the supplied registry, include evidence_refs, and do not create hard constraints."""


class ModelSuggestionGenerator:
    def __init__(self, llm=None, registry: RuleFieldRegistry | None = None) -> None:
        self.llm = llm
        self.registry = registry or RuleFieldRegistry()

    def generate(self, context: dict) -> list[ModelSuggestion]:
        if self.llm is None:
            return []
        structured = self.llm.with_structured_output(ModelSuggestionResult)
        result = structured.invoke({"instruction": MODEL_SUGGESTION_PROMPT, "registry_fields": [item.name for item in self.registry.all()], "context": context})
        valid = [item for item in result.suggestions if self.registry.exists(item.field) and item.evidence_refs]
        return valid[:5]
