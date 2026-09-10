from collections.abc import Iterable


def recall_at_k(rankings: Iterable[list[str]], expected: Iterable[set[str]], k: int = 5) -> float:
    pairs = list(zip(rankings, expected, strict=True))
    if not pairs:
        return 0.0
    return sum(bool(set(ranking[:k]) & gold) for ranking, gold in pairs) / len(pairs)


def mrr(rankings: Iterable[list[str]], expected: Iterable[set[str]]) -> float:
    pairs = list(zip(rankings, expected, strict=True))
    if not pairs:
        return 0.0
    total = 0.0
    for ranking, gold in pairs:
        total += next((1 / index for index, chunk_id in enumerate(ranking, start=1) if chunk_id in gold), 0.0)
    return total / len(pairs)


def no_evidence_abstention(predicted_evidence: Iterable[bool], answerable: Iterable[bool]) -> float:
    pairs = list(zip(predicted_evidence, answerable, strict=True))
    negative = [has_evidence for has_evidence, is_answerable in pairs if not is_answerable]
    if not negative:
        return 0.0
    return sum(not has_evidence for has_evidence in negative) / len(negative)


def citation_coverage(grounded_answers: Iterable[bool], has_citations: Iterable[bool]) -> float:
    pairs = list(zip(grounded_answers, has_citations, strict=True))
    grounded = [has_citation for is_grounded, has_citation in pairs if is_grounded]
    if not grounded:
        return 0.0
    return sum(grounded) / len(grounded)
