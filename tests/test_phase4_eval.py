from evals.research.run_research_eval import run


def test_phase4_fixed_evaluation_gates():
    metrics = run()
    assert metrics == {
        "search_plan_schema_validity": 1.0,
        "hard_constraint_coverage": 1.0,
        "budget_validity": 1.0,
        "case_count": 70,
    }
