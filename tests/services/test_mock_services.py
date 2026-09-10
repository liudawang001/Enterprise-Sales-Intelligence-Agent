from app.agent.dependencies import build_dependencies


def test_mock_services_are_offline_and_return_five_leads():
    deps = build_dependencies()
    set_id, leads = deps.research_service.discover(region="上海松江")
    assert set_id
    assert len(leads) == 5
    assert len(deps.research_service.get_candidates(set_id)) == 5
    scored = deps.scoring_service.score(leads, region="上海松江")
    assert scored[0].score == 100
