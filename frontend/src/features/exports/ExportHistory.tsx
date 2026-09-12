import { Download, FileSpreadsheet } from "lucide-react";
import type { ExportJob } from "../../types/export";
import { exportDownloadUrl } from "../../api/exports";
import { StatusBadge } from "../../components/StatusBadge";

export function ExportHistory({ items }: { items: ExportJob[] }) {
  if (!items.length) return <div className="empty-panel"><FileSpreadsheet size={24} /><strong>暂无导出记录</strong><span>从潜客列表生成固定版本 XLSX</span></div>;
  return <div className="export-history">{items.map((item) => <div key={item.export_id}><FileSpreadsheet size={19} /><div><strong>{item.file_name ?? "Excel 导出"}</strong><span>Task v{item.task_version} · {item.row_count ?? 0} 行 · {new Date(item.created_at).toLocaleString("zh-CN")}</span></div><StatusBadge value={item.status} />{item.status === "COMPLETED" && <a className="icon-button" title="下载" href={exportDownloadUrl(item.export_id)}><Download size={17} /></a>}</div>)}</div>;
}
