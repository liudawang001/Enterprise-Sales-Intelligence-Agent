import re


class CitationValidationError(ValueError):
    code = "UNKNOWN_CITATION"


class CitationValidator:
    def validate(self, answer: str, citations: list[dict]) -> str:
        allowed = {int(item["citation_id"]) for item in citations}
        references = {int(value) for value in re.findall(r"\[(\d+)\]", answer)}
        if not references.issubset(allowed):
            raise CitationValidationError(f"Unknown citation IDs: {sorted(references - allowed)}")
        return answer
