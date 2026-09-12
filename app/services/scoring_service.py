from app.domain.task import Lead
from app.scoring.engine import DeterministicScoringEngine
from app.scoring.explain import GroundedScoreExplainer


class MockScoringService:
    def score(self, leads: list[Lead], *, region: str | None = None) -> list[Lead]:
        scored: list[Lead] = []
        for lead in leads:
            score = 0
            if (lead.office_count or 0) > 1:
                score += 20
            if lead.industry in {"制造业", "物流"}:
                score += 20
            if lead.phone and lead.address:
                score += 20
            if region and lead.region == region:
                score += 20
            if lead.industry == "制造业":
                score += 20
            lead.score = float(min(score, 100))
            lead.recommendation_reason = f"该企业位于{lead.region}，联系方式完整，与当前集团V网模拟营销筛选规则匹配。"
            scored.append(lead)
        return sorted(scored, key=lambda item: item.score or 0, reverse=True)


class LeadScoringService:
    def __init__(self, repository, evidence_repository, enterprise_repository, rule_repository) -> None:
        self.repository = repository
        self.evidence_repository = evidence_repository
        self.enterprise_repository = enterprise_repository
        self.rule_repository = rule_repository
        self.engine = DeterministicScoringEngine()
        self.explainer = GroundedScoreExplainer()

    def score_task(self, *, task_id: str, criteria_id: str, profile_ids: list[str], target_count: int, task_version: int = 1) -> tuple[object, list[dict]]:
        criteria = self.rule_repository.criteria.get(criteria_id)
        if not criteria:
            raise ValueError("CRITERIA_NOT_FOUND")
        scoring_profile = self.repository.active_profile(criteria.business_code)
        if not scoring_profile:
            raise ValueError("SCORING_PROFILE_MISSING")
        scores = []
        rows = []
        for profile_id in profile_ids:
            profile = self.evidence_repository.profiles.get(profile_id)
            if not profile:
                continue
            score = self.repository.save_score(self.engine.score(task_id=task_id, profile=profile, criteria=criteria, scoring_profile=scoring_profile).model_copy(update={"task_version": task_version}))
            reason = self.repository.save_reason(
                self.explainer.explain(score), lead_score_id=score.lead_score_id
            )
            enterprise = self.enterprise_repository.get_enterprise(profile.enterprise_id)
            scores.append(score)
            rows.append({
                "enterprise_id": profile.enterprise_id,
                "company_name": enterprise.canonical_name if enterprise else profile.enterprise_id,
                "score": score.total_score,
                "rank_status": score.rank_status.value,
                "verification_status": score.verification_status,
                "evidence_coverage": score.evidence_coverage,
                "score_breakdown": [item.model_dump(mode="json") for item in score.component_scores],
                "recommendation_reason": reason.summary,
                "evidence_ids": reason.evidence_ids,
            })
        lead_set = self.repository.save_lead_set(self.engine.build_lead_set(task_id=task_id, criteria_snapshot_id=criteria_id, scoring_profile_id=scoring_profile.profile_id, scores=scores, top_n=target_count).model_copy(update={"task_version": task_version}))
        order = {enterprise_id: index for index, enterprise_id in enumerate(lead_set.lead_ids)}
        rows = [item for item in rows if item["enterprise_id"] in order]
        rows.sort(key=lambda item: (order.get(item["enterprise_id"], 10**9), -(item["score"] or 0)))
        return lead_set, rows
