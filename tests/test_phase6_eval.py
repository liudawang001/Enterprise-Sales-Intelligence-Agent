from evals.mutation.run_mutation_eval import run_evaluation


def test_phase6_mutation_evaluation_gates():
    report = run_evaluation()
    assert report.scope_case_count >= 50
    assert report.reuse_case_count >= 20
    assert report.version_case_count >= 20
    assert report.mutation_scope_accuracy == 1
    assert report.unsafe_under_reexecution_rate == 0
    assert report.unnecessary_full_replan_rate == 0
    assert report.artifact_reuse_correctness == 1
    assert report.version_fence_correctness == 1
    assert report.mutation_idempotency == 1
