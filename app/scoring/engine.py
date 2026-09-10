from __future__ import annotations

from app.criteria.models import LeadCriteria
from app.evidence.enums import FieldVerificationStatus
from app.evidence.models import VerifiedEnterpriseProfile
from app.scoring.components import calculate_component, evidence_ids, is_missing
from app.scoring.enums import LeadRankStatus, MissingFieldPolicy
from app.scoring.models import (
    LeadScore,
    ScoreComponentResult,
    ScoringProfile,
    VerifiedLeadSet,
)


class DeterministicScoringEngine:
    def score(self, *, task_id: str, profile: VerifiedEnterpriseProfile, criteria: LeadCriteria, scoring_profile: ScoringProfile) -> LeadScore:
        hard_missing = [name for name in scoring_profile.hard_required_fields if not profile.field(name) or profile.field(name).status in {FieldVerificationStatus.MISSING, FieldVerificationStatus.UNVERIFIED}]
        if hard_missing:
            return LeadScore(task_id=task_id, enterprise_id=profile.enterprise_id, criteria_snapshot_id=criteria.criteria_id, scoring_profile_id=scoring_profile.profile_id, scoring_profile_version=scoring_profile.version, evidence_coverage=profile.evidence_coverage, verification_status=profile.status.value, rank_status=LeadRankStatus.NOT_SCORABLE)
        active = []
        removed_weight = 0.0
        for component in scoring_profile.components:
            if component.component == "industry_preference" and not any(
                item.field == "industry" for item in criteria.soft_constraints
            ):
                removed_weight += component.weight
                continue
            if is_missing(profile, component.required_fields) and component.missing_policy == MissingFieldPolicy.REWEIGHT:
                removed_weight += component.weight
                continue
            active.append(component)
        factor = 100 / (100 - removed_weight) if removed_weight < 100 else 0
        results = []
        for component in active:
            missing = is_missing(profile, component.required_fields)
            if missing and component.missing_policy == MissingFieldPolicy.ZERO:
                raw, codes = 0.0, ["MISSING_ZERO"]
            elif missing and component.missing_policy == MissingFieldPolicy.NEUTRAL:
                raw, codes = 0.5, ["MISSING_NEUTRAL"]
            else:
                raw, codes = calculate_component(component, profile, criteria)
            effective_weight = component.weight * factor
            results.append(ScoreComponentResult(component=component.component, raw_score=round(raw, 6), weighted_score=round(raw * effective_weight, 4), weight=round(effective_weight, 4), reason_codes=codes, evidence_ids=evidence_ids(profile, component.required_fields)))
        total = round(sum(item.weighted_score for item in results), 2)
        rank_status = LeadRankStatus.SCORED if profile.evidence_coverage >= scoring_profile.min_evidence_coverage and profile.status != "CONFLICTING" else LeadRankStatus.PARTIAL_SCORE
        return LeadScore(task_id=task_id, enterprise_id=profile.enterprise_id, criteria_snapshot_id=criteria.criteria_id, scoring_profile_id=scoring_profile.profile_id, scoring_profile_version=scoring_profile.version, total_score=total, component_scores=results, evidence_coverage=profile.evidence_coverage, verification_status=profile.status.value, rank_status=rank_status)

    def build_lead_set(self, *, task_id: str, criteria_snapshot_id: str, scoring_profile_id: str, scores: list[LeadScore], top_n: int) -> VerifiedLeadSet:
        order = {LeadRankStatus.SCORED: 0, LeadRankStatus.PARTIAL_SCORE: 1, LeadRankStatus.NOT_SCORABLE: 2}
        ranked = sorted(scores, key=lambda item: (order[item.rank_status], -(item.total_score or 0), item.enterprise_id))
        ids = [item.enterprise_id for item in ranked if item.rank_status != LeadRankStatus.NOT_SCORABLE][:top_n]
        return VerifiedLeadSet(task_id=task_id, criteria_snapshot_id=criteria_snapshot_id, scoring_profile_id=scoring_profile_id, lead_ids=ids)
