from evals.rag.metrics import citation_coverage, mrr, no_evidence_abstention, recall_at_k


def test_retrieval_and_grounding_metrics() -> None:
    assert recall_at_k([["a", "b"]], [{"b"}], k=2) == 1.0
    assert mrr([["a", "b"]], [{"b"}]) == 0.5
    assert no_evidence_abstention([False, False, True], [False, False, False]) == 2 / 3
    assert citation_coverage([True, True, False], [True, True, False]) == 1.0
