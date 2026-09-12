import { ExternalLink } from "lucide-react";
import type { Evidence } from "../types/evidence";
import { StatusBadge } from "./StatusBadge";

function safeUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? value : null;
  } catch {
    return null;
  }
}

export function EvidenceTable({ evidence }: { evidence: Evidence[] }) {
  if (!evidence.length) return <div className="empty-compact">暂无可追溯证据</div>;
  return <div className="evidence-list">
    {evidence.map((item) => {
      const url = safeUrl(item.source_url);
      return <article className="evidence-item" key={item.evidence_id}>
        <div className="evidence-heading">
          <div><strong>{item.field_name}</strong><span>{item.source_type} · {item.provider}</span></div>
          <StatusBadge value={item.verification_role === "CONFLICTING" ? "CONFLICTING" : "VERIFIED"} />
        </div>
        <div className="evidence-value">{String(item.value ?? "MISSING")}</div>
        <div className="evidence-meta">
          <span>置信度 {(item.confidence * 100).toFixed(0)}%</span>
          <time>{new Date(item.retrieved_at).toLocaleString("zh-CN")}</time>
          {url ? <a href={url} target="_blank" rel="noopener noreferrer">来源 <ExternalLink size={13} /></a> : <span>无安全外链</span>}
        </div>
      </article>;
    })}
  </div>;
}
