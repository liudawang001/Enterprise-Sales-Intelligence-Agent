import json

from app.entities.enums import EntityRelationType
from app.entities.matcher import DeterministicEntityMatcher
from evals.entity.dataset import build_entity_pair_dataset


def evaluate() -> dict[str, float | int]:
    dataset = build_entity_pair_dataset()
    matcher = DeterministicEntityMatcher()
    expected = [label for _, _, label in dataset]
    predicted = [matcher.match(left, right).relation for left, right, _ in dataset]
    tp = sum(p == e == EntityRelationType.SAME_ENTITY for p, e in zip(predicted, expected, strict=True))
    fp = sum(p == EntityRelationType.SAME_ENTITY and e != EntityRelationType.SAME_ENTITY for p, e in zip(predicted, expected, strict=True))
    fn = sum(p != EntityRelationType.SAME_ENTITY and e == EntityRelationType.SAME_ENTITY for p, e in zip(predicted, expected, strict=True))
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    hard_negative = sum(p == e == EntityRelationType.DIFFERENT for p, e in zip(predicted, expected, strict=True)) / sum(e == EntityRelationType.DIFFERENT for e in expected)
    return {
        "cases": len(dataset),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0,
        "same_entity_precision": precision,
        "different_credit_code_hard_negative_accuracy": hard_negative,
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
