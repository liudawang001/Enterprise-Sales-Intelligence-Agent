from app.domain.task import Lead


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
