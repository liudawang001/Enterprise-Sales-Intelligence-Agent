from evals.entity.run_entity_eval import evaluate as evaluate_entity
from evals.phase5.run_evidence_scoring_eval import evaluate


def test_phase5_evaluation_gates():
    entity = evaluate_entity()
    phase5 = evaluate()
    assert entity["cases"] >= 50
    assert entity["same_entity_precision"] >= 0.95
    assert entity["different_credit_code_hard_negative_accuracy"] == 1
    assert phase5["evidence"]["cases"] >= 30
    assert phase5["evidence"]["conflict_detection_accuracy"] == 1
    assert phase5["evidence"]["primary_value_selection_accuracy"] == 1
    assert phase5["evidence"]["source_traceability"] == 1
    assert phase5["scoring"]["cases"] >= 30
    assert phase5["scoring"]["determinism"] == 1
    assert phase5["scoring"]["monotonicity"] == 1
    assert phase5["scoring"]["profile_reproducibility"] == 1
    assert phase5["scoring"]["hard_required_missing_not_scorable"] == 1
