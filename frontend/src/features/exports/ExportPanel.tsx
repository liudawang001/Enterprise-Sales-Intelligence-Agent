import { Download, FileSpreadsheet, LoaderCircle, X } from "lucide-react";
import type { ExportField, ExportJob } from "../../types/export";
import { exportDownloadUrl } from "../../api/exports";

export function ExportPanel({ fields, selected, topN, maxRows, options, job, error, busy, onSelected, onTopN, onOptions, onSubmit, onClose }: {
  fields: ExportField[];
  selected: Set<string>;
  topN: number;
  maxRows: number;
  options: { score: boolean; evidence: boolean; conflicts: boolean; task: boolean };
  job?: ExportJob;
  error?: string;
  busy: boolean;
  onSelected: (value: Set<string>) => void;
  onTopN: (value: number) => void;
  onOptions: (value: { score: boolean; evidence: boolean; conflicts: boolean; task: boolean }) => void;
  onSubmit: () => void;
  onClose: () => void;
}) {
  return <div className="drawer-backdrop" role="presentation" onMouseDown={onClose}><aside className="export-panel" role="dialog" aria-modal="true" aria-label="导出 Excel" onMouseDown={(event) => event.stopPropagation()}>
    <header><div><span className="eyebrow">固定版本交付</span><h2>导出 Excel</h2></div><button className="icon-button" title="关闭" onClick={onClose}><X size={20} /></button></header>
    <div className="export-content">
      <label className="number-field"><span>导出前 N 条</span><input type="number" min={1} max={maxRows} value={topN} onChange={(event) => onTopN(Math.min(maxRows, Math.max(1, Number(event.target.value))))} /></label>
      <fieldset><legend>潜客清单字段</legend><div className="field-picker">{fields.map((field) => <label key={field.field_key}><input type="checkbox" checked={selected.has(field.field_key)} onChange={(event) => { const next = new Set(selected); event.target.checked ? next.add(field.field_key) : next.delete(field.field_key); onSelected(next); }} /><span>{field.display_name}</span></label>)}</div></fieldset>
      <fieldset><legend>附加 Sheet</legend><div className="sheet-options">
        <label><input type="checkbox" checked={options.score} onChange={(event) => onOptions({ ...options, score: event.target.checked })} />评分说明</label>
        <label><input type="checkbox" checked={options.evidence} onChange={(event) => onOptions({ ...options, evidence: event.target.checked })} />证据摘要</label>
        <label><input type="checkbox" checked={options.conflicts} onChange={(event) => onOptions({ ...options, conflicts: event.target.checked })} />冲突明细</label>
        <label><input type="checkbox" checked={options.task} onChange={(event) => onOptions({ ...options, task: event.target.checked })} />任务信息</label>
      </div></fieldset>
      {error && <div className="inline-error">{error}</div>}
      {job?.status === "COMPLETED" && <div className="export-complete"><FileSpreadsheet size={22} /><div><strong>{job.file_name}</strong><span>{job.row_count} 行 · SHA256 {job.sha256?.slice(0, 12)}</span></div><a className="icon-button" title="下载" href={exportDownloadUrl(job.export_id)}><Download size={19} /></a></div>}
    </div>
    <footer><button className="secondary-button" onClick={onClose}>取消</button><button className="primary-button" disabled={busy || !selected.size} onClick={onSubmit}>{busy ? <LoaderCircle className="spin" size={17} /> : <FileSpreadsheet size={17} />}生成 XLSX</button></footer>
  </aside></div>;
}
