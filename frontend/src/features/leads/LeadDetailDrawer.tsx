import { Building2, MapPin, Network, Phone, X } from "lucide-react";
import type { LeadDetail } from "../../types/lead";
import { EvidenceTable } from "../../components/EvidenceTable";
import { ScoreBreakdown } from "../../components/ScoreBreakdown";
import { StatusBadge } from "../../components/StatusBadge";

export function LeadDetailDrawer({ detail, loading, onClose }: { detail?: LeadDetail; loading: boolean; onClose: () => void }) {
  return <div className="drawer-backdrop" role="presentation" onMouseDown={onClose}>
    <aside className="lead-drawer" role="dialog" aria-modal="true" aria-label="潜客详情" onMouseDown={(event) => event.stopPropagation()}>
      <header><div><span className="eyebrow">潜客 #{detail?.lead.rank ?? ""}</span><h2>{detail?.lead.enterprise_name ?? "正在加载"}</h2></div><button className="icon-button" onClick={onClose} title="关闭"><X size={20} /></button></header>
      {loading || !detail ? <div className="drawer-loading">正在读取固定版本详情...</div> : <div className="drawer-content">
        <div className="detail-summary"><StatusBadge value={detail.lead.verification_status} /><strong>{detail.lead.lead_score?.toFixed(1) ?? "n.a."} 分</strong><span>Task v{detail.task_version}</span></div>
        <section><h3>企业档案</h3><dl className="profile-grid">
          <div><dt><Building2 size={14} />行业</dt><dd>{detail.lead.industry ?? "MISSING"}</dd></div>
          <div><dt><MapPin size={14} />区域</dt><dd>{detail.lead.region ?? "MISSING"}</dd></div>
          <div><dt><Phone size={14} />公开电话</dt><dd>{detail.lead.public_phone ?? "MISSING"} <StatusBadge value={detail.lead.field_statuses.public_phone ?? "MISSING"} /></dd></div>
          <div><dt><Network size={14} />官网</dt><dd>{detail.lead.website ?? "MISSING"} <StatusBadge value={detail.lead.field_statuses.website ?? "MISSING"} /></dd></div>
        </dl></section>
        <section><h3>推荐理由</h3><p className="reason">{detail.score.recommendation_reason ?? "暂无已生成的推荐理由"}</p></section>
        <ScoreBreakdown score={detail.score} />
        <section><h3>字段核验</h3><div className="field-list">{detail.resolved_fields.map((field) => <div key={field.resolved_field_id}><span>{field.field_name}</span><strong>{String(field.primary_value ?? "MISSING")}</strong><StatusBadge value={field.status} /></div>)}</div></section>
        <section><h3>证据与冲突</h3><EvidenceTable evidence={detail.evidence} /></section>
        <section><h3>地点与关系</h3><p className="reason">地点 {detail.locations.length} 个，企业关系 {detail.relations.length} 条。所有信息来自当前冻结版本。</p></section>
      </div>}
    </aside>
  </div>;
}
