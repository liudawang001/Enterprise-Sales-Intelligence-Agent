from app.entities.blocking import EntityBlocker
from app.entities.enums import EntityRelationType
from app.entities.matcher import DeterministicEntityMatcher
from app.entities.models import AmbiguousResolutionResult
from app.entities.normalizer import (
    AddressNormalizer,
    EnterpriseNameNormalizer,
    PhoneNormalizer,
    WebsiteNormalizer,
)
from app.research.models import RawEnterpriseCandidate


def candidate(name: str, **updates) -> RawEnterpriseCandidate:
    return RawEnterpriseCandidate(
        research_run_id="run",
        source_provider="fixture",
        source_name=name,
        normalized_name=name,
        **updates,
    )


def test_identity_normalizers_preserve_entity_markers_and_normalize_contacts():
    name = EnterpriseNameNormalizer().normalize("上海 ABC 科技有限公司（浦东分公司）")
    assert name.base_name == "abc科技"
    assert name.legal_suffix == "有限公司"
    assert name.branch_marker == "分公司"
    assert AddressNormalizer().normalize("上海市 上海市 松江区 A路1号") == "上海市松江区a路1号"
    assert PhoneNormalizer().normalize("+86 (021) 5555-0000 转 123") == "02155550000x123"
    assert WebsiteNormalizer().normalize("HTTPS://WWW.Example.COM/") == "example.com"


def test_same_and_different_credit_codes_are_hard_decisions():
    matcher = DeterministicEntityMatcher()
    left = candidate("上海ABC科技有限公司", unified_social_credit_code="X")
    same = candidate("ABC", unified_social_credit_code="X")
    different = candidate("上海ABC科技有限公司", unified_social_credit_code="Y")
    assert matcher.match(left, same).relation == EntityRelationType.SAME_ENTITY
    decision = matcher.match(left, different)
    assert decision.relation == EntityRelationType.DIFFERENT
    assert decision.hard_negatives == ["DIFFERENT_CREDIT_CODE"]
    assert not decision.llm_used


def test_branch_and_office_are_relations_not_same_entity():
    matcher = DeterministicEntityMatcher()
    parent = candidate("ABC科技有限公司")
    branch = candidate("ABC科技有限公司上海分公司")
    office = candidate("ABC科技有限公司办事处")
    assert matcher.match(parent, branch).relation == EntityRelationType.BRANCH_OF
    assert matcher.match(parent, office).relation == EntityRelationType.OFFICE_OF


def test_same_domain_and_name_is_same_and_blocked_together():
    left = candidate("上海ABC科技有限公司", website_candidate="https://www.example.com")
    right = candidate("上海ABC科技股份有限公司", website_candidate="http://example.com/")
    groups = EntityBlocker().build_groups([left, right])
    assert groups
    assert DeterministicEntityMatcher().match(left, right).relation == EntityRelationType.SAME_ENTITY


def test_hard_negative_never_calls_ambiguous_resolver():
    class MustNotRun:
        def resolve(self, left, right, signals):
            raise AssertionError("LLM resolver must not override a hard negative")

    matcher = DeterministicEntityMatcher(MustNotRun())
    result = matcher.match(
        candidate("同名公司", unified_social_credit_code="A"),
        candidate("同名公司", unified_social_credit_code="B"),
    )
    assert result.relation == EntityRelationType.DIFFERENT


def test_llm_is_only_used_inside_ambiguous_band():
    class FakeResolver:
        def __init__(self):
            self.called = False

        def resolve(self, left, right, signals):
            self.called = True
            return AmbiguousResolutionResult(
                relation=EntityRelationType.POSSIBLY_RELATED, reason="fixture"
            )

    resolver = FakeResolver()
    matcher = DeterministicEntityMatcher(resolver)
    result = matcher.match(
        candidate("上海远景科技", public_phone="021-55550000"),
        candidate("上海远景科技服务", public_phone="021 5555 0000"),
    )
    assert resolver.called and result.llm_used
