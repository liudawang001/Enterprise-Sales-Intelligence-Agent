import pytest

from app.criteria.models import LeadCriteria
from app.evidence.models import ResolvedField, VerifiedEnterpriseProfile
from app.repositories.lead_score_repository import InMemoryLeadScoreRepository
from app.scoring.engine import DeterministicScoringEngine
from app.scoring.enums import LeadRankStatus
from app.scoring.explain import GroundedScoreExplainer
from app.scoring.models import RecommendationReason
from app.scoring.profiles import demo_scoring_profiles


def field(name, value, *, status="VERIFIED", confidence=0.9):
    return ResolvedField(
        enterprise_id="enterprise",
        field_name=name,
        primary_value=value,
        status=status,
        confidence=confidence,
        supporting_evidence_ids=[f"evidence-{name}"],
    )


def profile(*, office_count=2, coverage=1, omit=(), conflicting=()):
    values = {
        "legal_name": field("legal_name", "上海ABC科技有限公司"),
        "company_status": field("company_status", "正常"),
        "office_count": field("office_count", office_count),
        "cross_region_presence": field("cross_region_presence", True),
        "company_scale": field("company_scale", "LARGE"),
        "employee_count": field("employee_count", 300),
        "industry": field("industry", "制造业"),
        "address": field("address", "上海松江区A路1号"),
        "public_phone": field("public_phone", "021-1111"),
        "website": field("website", "example.com"),
    }
    for name in omit:
        values.pop(name)
    for name in conflicting:
        values[name] = values[name].model_copy(update={"status": "CONFLICTING", "confidence": 0.5})
    return VerifiedEnterpriseProfile(
        verification_run_id="verification",
        enterprise_id="enterprise",
        fields=values,
        status="CONFLICTING" if conflicting else "VERIFIED",
        evidence_coverage=coverage,
        required_fields=list(values),
    )


def criteria():
    return LeadCriteria(
        criteria_id="criteria",
        task_id="task",
        task_version=1,
        business_code="GROUP_VNET",
        region_scope=["上海松江"],
        target_count=10,
        soft_constraints=[{"field": "industry", "operator": "EQ", "value": "制造业"}],
    )


def test_scoring_is_deterministic_and_weights_total_100():
    engine = DeterministicScoringEngine()
    scoring_profile = demo_scoring_profiles()[0]
    first = engine.score(task_id="task", profile=profile(), criteria=criteria(), scoring_profile=scoring_profile)
    second = engine.score(task_id="task", profile=profile(), criteria=criteria(), scoring_profile=scoring_profile)
    assert first.total_score == second.total_score
    assert round(sum(item.weight for item in first.component_scores), 4) == 100
    assert first.rank_status == LeadRankStatus.SCORED


def test_office_score_is_monotonic():
    engine = DeterministicScoringEngine()
    scoring_profile = demo_scoring_profiles()[0]
    low = engine.score(task_id="task", profile=profile(office_count=1), criteria=criteria(), scoring_profile=scoring_profile)
    high = engine.score(task_id="task", profile=profile(office_count=5), criteria=criteria(), scoring_profile=scoring_profile)
    low_component = next(item for item in low.component_scores if item.component == "office_distribution")
    high_component = next(item for item in high.component_scores if item.component == "office_distribution")
    assert high_component.weighted_score >= low_component.weighted_score


def test_missing_reweight_and_hard_required_not_scorable():
    engine = DeterministicScoringEngine()
    scoring_profile = demo_scoring_profiles()[0]
    reweighted = engine.score(task_id="task", profile=profile(omit=("industry", "company_scale", "employee_count")), criteria=criteria(), scoring_profile=scoring_profile)
    assert round(sum(item.weight for item in reweighted.component_scores), 4) == 100
    unscorable = engine.score(task_id="task", profile=profile(omit=("legal_name",)), criteria=criteria(), scoring_profile=scoring_profile)
    assert unscorable.rank_status == LeadRankStatus.NOT_SCORABLE
    assert unscorable.total_score is None


def test_conflict_and_low_coverage_produce_partial_score():
    engine = DeterministicScoringEngine()
    result = engine.score(task_id="task", profile=profile(coverage=0.3, conflicting=("public_phone",)), criteria=criteria(), scoring_profile=demo_scoring_profiles()[0])
    assert result.rank_status == LeadRankStatus.PARTIAL_SCORE
    contact = next(item for item in result.component_scores if item.component == "contact_completeness")
    assert contact.raw_score < 1


def test_profile_version_is_idempotent_but_immutable():
    repository = InMemoryLeadScoreRepository()
    original = demo_scoring_profiles()[0]
    repository.save_profile(original)
    duplicate = original.model_copy(update={"profile_id": "another-id"})
    assert repository.save_profile(duplicate).profile_id == original.profile_id
    changed = original.model_copy(update={"profile_id": "changed", "min_evidence_coverage": 0.9})
    with pytest.raises(ValueError, match="IMMUTABLE"):
        repository.save_profile(changed)


def test_grounded_explanation_rejects_illegal_evidence_id():
    score = DeterministicScoringEngine().score(task_id="task", profile=profile(), criteria=criteria(), scoring_profile=demo_scoring_profiles()[0])

    class InvalidModel:
        def explain(self, payload):
            return RecommendationReason(enterprise_id="enterprise", summary="invalid", evidence_ids=["invented"])

    with pytest.raises(ValueError, match="ILLEGAL_EVIDENCE_ID"):
        GroundedScoreExplainer(InvalidModel()).explain(score)
