from __future__ import annotations

from typing import Protocol

from app.scoring.models import LeadScore, RecommendationReason


class ExplanationModel(Protocol):
    def explain(self, payload: dict) -> RecommendationReason: ...


class GroundedScoreExplainer:
    def __init__(self, model: ExplanationModel | None = None) -> None:
        self.model = model

    def explain(self, score: LeadScore) -> RecommendationReason:
        allowed_ids = {evidence_id for item in score.component_scores for evidence_id in item.evidence_ids}
        reason_codes = sorted({code for item in score.component_scores for code in item.reason_codes})
        if self.model:
            result = self.model.explain({
                "instruction": "Do not recalculate score. Do not invent facts. Use only provided verified fields and evidence IDs.",
                "enterprise_id": score.enterprise_id,
                "total_score": score.total_score,
                "rank_status": score.rank_status.value,
                "components": [item.model_dump(mode="json") for item in score.component_scores],
                "allowed_evidence_ids": sorted(allowed_ids),
            })
        else:
            conflict = score.verification_status == "CONFLICTING"
            suffix = "；部分字段存在冲突，结论需谨慎使用" if conflict else ""
            result = RecommendationReason(enterprise_id=score.enterprise_id, summary=f"确定性评分为 {score.total_score}，状态为 {score.rank_status.value}{suffix}", reason_codes=reason_codes, evidence_ids=sorted(allowed_ids))
        illegal = set(result.evidence_ids) - allowed_ids
        if illegal:
            raise ValueError(f"ILLEGAL_EVIDENCE_ID: {sorted(illegal)}")
        if result.enterprise_id != score.enterprise_id:
            raise ValueError("explanation enterprise does not match score")
        return result
