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
