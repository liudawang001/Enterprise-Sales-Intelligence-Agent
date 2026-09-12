import { ChevronLeft, ChevronRight, Columns3, ExternalLink, Search } from "lucide-react";
import type { DeliveryLead, LeadPage } from "../../types/lead";
import { StatusBadge } from "../../components/StatusBadge";

export interface LeadFilters {
  verification_status: string;
  min_score: string;
  industry: string;
  has_public_phone: string;
  has_website: string;
}

const columns = [
  ["industry", "行业"],
  ["company_scale", "规模"],
  ["region", "区域"],
  ["office_count", "办公点"],
  ["public_phone", "公开电话"],
  ["website", "官网"]
] as const;

function safeUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? value : null;
  } catch {
    return null;
  }
}

export function LeadTable({ data, filters, visible, onFilters, onVisible, onPage, onSort, onSelect }: {
  data?: LeadPage;
  filters: LeadFilters;
  visible: Set<string>;
  onFilters: (filters: LeadFilters) => void;
  onVisible: (visible: Set<string>) => void;
  onPage: (page: number) => void;
  onSort: (sortBy: string) => void;
  onSelect: (lead: DeliveryLead) => void;
}) {
  const update = (key: keyof LeadFilters, value: string) => onFilters({ ...filters, [key]: value });
  return <section className="lead-section" aria-label="潜客列表">
    <div className="lead-toolbar">
      <label className="filter-search"><Search size={15} /><input aria-label="最低评分" inputMode="decimal" placeholder="最低分" value={filters.min_score} onChange={(event) => update("min_score", event.target.value)} /></label>
      <select aria-label="核验状态" value={filters.verification_status} onChange={(event) => update("verification_status", event.target.value)}>
        <option value="">全部状态</option><option value="VERIFIED">已核验</option><option value="PARTIAL">部分核验</option><option value="CONFLICTING">存在冲突</option><option value="UNVERIFIED">未核验</option>
      </select>
      <input aria-label="行业筛选" placeholder="行业" value={filters.industry} onChange={(event) => update("industry", event.target.value)} />
      <select aria-label="联系电话筛选" value={filters.has_public_phone} onChange={(event) => update("has_public_phone", event.target.value)}><option value="">电话不限</option><option value="true">有公开电话</option><option value="false">无公开电话</option></select>
      <select aria-label="官网筛选" value={filters.has_website} onChange={(event) => update("has_website", event.target.value)}><option value="">官网不限</option><option value="true">有官网</option><option value="false">无官网</option></select>
      <details className="column-picker"><summary title="显示列"><Columns3 size={16} /><span>列</span></summary><div>{columns.map(([key, label]) => <label key={key}><input type="checkbox" checked={visible.has(key)} onChange={(event) => { const next = new Set(visible); event.target.checked ? next.add(key) : next.delete(key); onVisible(next); }} />{label}</label>)}</div></details>
    </div>
    <div className="quality-strip">
      <span><strong>{data?.total ?? 0}</strong> 条结果</span>
      <span>已核验 {data?.quality_summary.VERIFIED ?? 0}</span>
      <span>部分核验 {data?.quality_summary.PARTIAL ?? 0}</span>
      <span>冲突 {data?.quality_summary.CONFLICTING ?? 0}</span>
      <span>证据覆盖 {Math.round((data?.quality_summary.evidence_coverage ?? 0) * 100)}%</span>
    </div>
    <div className="table-scroll"><table>
      <thead><tr>
        <th><button onClick={() => onSort("rank")}>{data?.view_sort ? "正式排名" : "排名"}</button></th>
        <th>企业</th>
        {visible.has("industry") && <th><button onClick={() => onSort("industry")}>行业</button></th>}
        {visible.has("company_scale") && <th>规模</th>}
        {visible.has("region") && <th>区域</th>}
        {visible.has("office_count") && <th><button onClick={() => onSort("office_count")}>办公点</button></th>}
        <th><button onClick={() => onSort("lead_score")}>评分</button></th><th>核验</th>
        {visible.has("public_phone") && <th>公开电话</th>}
        {visible.has("website") && <th>官网</th>}
      </tr></thead>
      <tbody>{data?.items.map((lead) => <tr key={lead.enterprise_id} onClick={() => onSelect(lead)}>
        <td className="rank-cell">{lead.rank}</td><td><button className="company-link" onClick={() => onSelect(lead)}>{lead.enterprise_name}</button></td>
        {visible.has("industry") && <td>{lead.industry ?? "MISSING"}</td>}
        {visible.has("company_scale") && <td>{lead.company_scale ?? "MISSING"}</td>}
        {visible.has("region") && <td>{lead.region ?? "MISSING"}</td>}
        {visible.has("office_count") && <td>{lead.office_count ?? "MISSING"}</td>}
        <td className="score-cell">{lead.lead_score?.toFixed(1) ?? "n.a."}</td><td><StatusBadge value={lead.verification_status} /></td>
        {visible.has("public_phone") && <td>{lead.public_phone ?? "MISSING"}</td>}
        {visible.has("website") && <td>{safeUrl(lead.website) ? <a href={safeUrl(lead.website)!} target="_blank" rel="noopener noreferrer" onClick={(event) => event.stopPropagation()} aria-label={`打开 ${lead.enterprise_name} 官网`}><ExternalLink size={15} /></a> : lead.website ?? "MISSING"}</td>}
      </tr>)}</tbody>
    </table></div>
    <footer className="pagination"><span>第 {data?.page ?? 1} / {data?.total_pages || 1} 页</span><div><button title="上一页" disabled={!data || data.page <= 1} onClick={() => onPage((data?.page ?? 1) - 1)}><ChevronLeft size={17} /></button><button title="下一页" disabled={!data || data.page >= data.total_pages} onClick={() => onPage((data?.page ?? 1) + 1)}><ChevronRight size={17} /></button></div></footer>
  </section>;
}
