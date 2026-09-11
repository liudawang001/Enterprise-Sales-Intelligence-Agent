import type { ScoreExplain } from "../types/lead";

const labels: Record<string, string> = {
  business_fit: "业务匹配",
  office_distribution: "办公分布",
  company_scale: "企业规模",
  industry_preference: "行业偏好",
  location_fit: "区域匹配",
  evidence_confidence: "证据置信",
  contact_completeness: "联系方式完整度"
};

export function ScoreBreakdown({ score }: { score: ScoreExplain }) {
  return <section className="score-section" aria-label="评分拆解">
    <div className="score-total"><span>总分</span><strong>{score.total_score?.toFixed(1) ?? "n.a."}</strong><small>Profile v{score.scoring_profile_version}</small></div>
    <div className="score-components">
      {score.components.map((item) => <div className="score-row" key={item.component}>
        <div><span>{labels[item.component] ?? item.component}</span><strong>{item.weighted_score.toFixed(1)}</strong></div>
        <div className="score-track"><span style={{ width: `${Math.min(100, item.raw_score * 100)}%` }} /></div>
        <small>权重 {item.weight.toFixed(0)}%</small>
      </div>)}
    </div>
  </section>;
}
