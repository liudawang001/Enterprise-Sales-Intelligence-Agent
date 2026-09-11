import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, FileSpreadsheet, Menu, MessageSquareText, PanelLeft, Send, UsersRound } from "lucide-react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { activateTask, getTask, getTasks, getTaskVersions, sendChat } from "../api/tasks";
import { getLead, getLeads } from "../api/leads";
import { createExport, getExportFields, getExports } from "../api/exports";
import { InterruptCard } from "../components/InterruptCard";
import { ProgressTimeline } from "../components/ProgressTimeline";
import { StatusBadge } from "../components/StatusBadge";
import { ExportHistory } from "../features/exports/ExportHistory";
import { ExportPanel } from "../features/exports/ExportPanel";
import { LeadDetailDrawer } from "../features/leads/LeadDetailDrawer";
import { LeadTable, type LeadFilters } from "../features/leads/LeadTable";
import { TaskList } from "../features/tasks/TaskList";
import { TaskVersionSelector } from "../features/tasks/TaskVersionSelector";
import { useTaskEvents } from "../hooks/useTaskEvents";
import type { ChatResponse, TaskSummary } from "../types/task";

type MobileTab = "tasks" | "conversation" | "leads";

export function WorkspacePage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [mobileTab, setMobileTab] = useState<MobileTab>("leads");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Array<{ role: "user" | "agent"; text: string }>>([]);
  const [interrupt, setInterrupt] = useState<ChatResponse["interrupt"]>();
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState({ by: "rank", order: "asc" });
  const [filters, setFilters] = useState<LeadFilters>({ verification_status: "", min_score: "", industry: "", has_public_phone: "", has_website: "" });
  const [visible, setVisible] = useState(new Set(["industry", "company_scale", "region", "office_count", "public_phone", "website"]));
  const [selectedLead, setSelectedLead] = useState<string>();
  const [showExport, setShowExport] = useState(false);
  const [exportFields, setExportFields] = useState(new Set(["rank", "enterprise_name", "lead_score", "verification_status"]));
  const [topN, setTopN] = useState(1);
  const [exportOptions, setExportOptions] = useState({ score: true, evidence: true, conflicts: true, task: true });

  const tasksQuery = useQuery({ queryKey: ["tasks"], queryFn: () => getTasks() });
  const selectedTask = tasksQuery.data?.find((task) => task.task_id === params.taskId) ?? tasksQuery.data?.find((task) => task.active) ?? tasksQuery.data?.[0];
  const version = Number(searchParams.get("version")) || selectedTask?.current_version || 1;
  const taskQuery = useQuery({ queryKey: ["task", selectedTask?.task_id], queryFn: () => getTask(selectedTask!.task_id), enabled: Boolean(selectedTask) });
  const versionsQuery = useQuery({ queryKey: ["versions", selectedTask?.task_id], queryFn: () => getTaskVersions(selectedTask!.task_id), enabled: Boolean(selectedTask) });
  const leadsQuery = useQuery({
    queryKey: ["leads", selectedTask?.task_id, version, page, sort, filters],
    queryFn: () => getLeads(selectedTask!.task_id, version, {
      page,
      page_size: 20,
      sort_by: sort.by,
      sort_order: sort.order,
      verification_status: filters.verification_status || undefined,
      min_score: filters.min_score ? Number(filters.min_score) : undefined,
      industry: filters.industry || undefined,
      has_public_phone: filters.has_public_phone ? filters.has_public_phone === "true" : undefined,
      has_website: filters.has_website ? filters.has_website === "true" : undefined
    }),
    enabled: Boolean(selectedTask)
  });
  const detailQuery = useQuery({ queryKey: ["lead", selectedTask?.task_id, version, selectedLead], queryFn: () => getLead(selectedTask!.task_id, version, selectedLead!), enabled: Boolean(selectedTask && selectedLead) });
  const fieldsQuery = useQuery({ queryKey: ["export-fields"], queryFn: getExportFields });
  const exportsQuery = useQuery({ queryKey: ["exports", selectedTask?.task_id], queryFn: () => getExports(selectedTask!.task_id), enabled: Boolean(selectedTask) });
  const progress = useTaskEvents(selectedTask?.task_id);

  const chatMutation = useMutation({
    mutationFn: (text: string) => sendChat(selectedTask?.session_id ?? "workspace-demo", text),
    onSuccess: async (response, text) => {
      setMessages((items) => [...items, { role: "user", text }, ...(response.message ? [{ role: "agent" as const, text: response.message }] : [])]);
      setInterrupt(response.interrupt);
      await queryClient.invalidateQueries();
      if (response.task_id) navigate(`/tasks/${response.task_id}`);
    }
  });
  const activateMutation = useMutation({ mutationFn: (task: TaskSummary) => activateTask(task.task_id, task.session_id), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }) });
  const exportMutation = useMutation({
    mutationFn: () => createExport({ task_id: selectedTask!.task_id, task_version: version, snapshot_id: leadsQuery.data?.snapshot_id, target_count: topN, fields: [...exportFields], include_task_summary: exportOptions.task, include_score_breakdown: exportOptions.score, include_evidence_summary: exportOptions.evidence, include_conflicts: exportOptions.conflicts }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["exports", selectedTask?.task_id] })
  });

  const currentSummary = taskQuery.data?.summary ?? selectedTask;
  const historical = Boolean(selectedTask && version !== selectedTask.current_version);
  const orderedMessages = useMemo(() => messages.slice(-12), [messages]);

  const selectTask = (task: TaskSummary) => {
    navigate(`/tasks/${task.task_id}`);
    setSearchParams({ version: String(task.current_version) });
    setPage(1);
    setSelectedLead(undefined);
    if (!task.active) activateMutation.mutate(task);
  };
  const submitMessage = (text: string) => {
    const clean = text.trim();
    if (!clean || chatMutation.isPending) return;
    setMessage("");
    chatMutation.mutate(clean);
  };
  const changeSort = (by: string) => {
    setSort((value) => value.by === by ? { by, order: value.order === "asc" ? "desc" : "asc" } : { by, order: by === "lead_score" ? "desc" : "asc" });
    setPage(1);
  };

  return <div className="app-shell">
    <header className="app-header">
      <div className="brand"><span className="brand-mark"><Bot size={20} /></span><div><strong>政企营销智能体</strong><span>Enterprise Sales Intelligence</span></div></div>
      <div className="header-context">{selectedTask ? <><span>{selectedTask.business}</span><span>{selectedTask.region}</span><StatusBadge value={selectedTask.status} /></> : <span>等待创建任务</span>}</div>
      <button className="icon-button mobile-only" title="导航"><Menu size={19} /></button>
    </header>
    <div className="mobile-tabs" role="tablist">
      <button className={mobileTab === "tasks" ? "active" : ""} onClick={() => setMobileTab("tasks")}><PanelLeft size={16} />任务</button>
      <button className={mobileTab === "conversation" ? "active" : ""} onClick={() => setMobileTab("conversation")}><MessageSquareText size={16} />对话</button>
      <button className={mobileTab === "leads" ? "active" : ""} onClick={() => setMobileTab("leads")}><UsersRound size={16} />潜客</button>
    </div>
    <main className="workspace-grid">
      <aside className={`workspace-pane task-pane ${mobileTab === "tasks" ? "mobile-active" : ""}`}>
        <div className="pane-header"><div><span className="eyebrow">任务空间</span><h1>营销任务</h1></div><span className="count">{tasksQuery.data?.length ?? 0}</span></div>
        <TaskList tasks={tasksQuery.data ?? []} selectedId={selectedTask?.task_id} onSelect={selectTask} />
      </aside>
      <section className={`workspace-pane conversation-pane ${mobileTab === "conversation" ? "mobile-active" : ""}`}>
        <div className="pane-header"><div><span className="eyebrow">当前上下文</span><h2>{currentSummary?.business ?? "对话下达任务"}</h2></div>{selectedTask && <TaskVersionSelector versions={versionsQuery.data ?? []} value={version} current={selectedTask.current_version} onChange={(next) => { setSearchParams({ version: String(next) }); setPage(1); setSelectedLead(undefined); }} />}</div>
        {historical && <div className="historical-banner">Historical Version · 只读查看 v{version}</div>}
        {currentSummary && <section className="task-summary">
          <div><span>业务</span><strong>{currentSummary.business ?? "待补充"}</strong></div><div><span>地区</span><strong>{currentSummary.region ?? "待补充"}</strong></div><div><span>目标</span><strong>Top {currentSummary.target_count ?? "?"}</strong></div><div><span>结果</span><strong>{currentSummary.result_count}</strong></div>
          {currentSummary.current_mutation_scope && <div className="mutation-summary"><span>最近变更</span><strong>{currentSummary.current_mutation_scope}</strong></div>}
        </section>}
        {selectedTask && <ProgressTimeline stage={progress?.stage ?? selectedTask.stage} completed={(progress?.status ?? selectedTask.status) === "COMPLETED"} />}
        <div className="conversation-log" aria-live="polite">
          {orderedMessages.length ? orderedMessages.map((item, index) => <div key={`${item.role}-${index}`} className={`message ${item.role}`}><span>{item.role === "user" ? "你" : "Agent"}</span><p>{item.text}</p></div>) : <div className="conversation-empty"><MessageSquareText size={24} /><strong>输入一条营销任务</strong><span>例如：帮我找上海松江 30 家集团 V 网潜客</span></div>}
          {interrupt && <InterruptCard interrupt={interrupt} onSubmit={(value) => { setInterrupt(undefined); submitMessage(value); }} />}
          {chatMutation.error && <div className="inline-error">{chatMutation.error.message}</div>}
        </div>
        {!historical && <form className="chat-composer" onSubmit={(event) => { event.preventDefault(); submitMessage(message); }}><textarea aria-label="对话输入" rows={2} placeholder="描述新任务、修改条件或询问评分原因" value={message} onChange={(event) => setMessage(event.target.value)} /><button className="primary-icon" type="submit" title="发送" disabled={!message.trim() || chatMutation.isPending}><Send size={18} /></button></form>}
      </section>
      <section className={`workspace-pane leads-pane ${mobileTab === "leads" ? "mobile-active" : ""}`}>
        <div className="pane-header leads-header"><div><span className="eyebrow">Task v{version}</span><h2>潜客结果</h2></div><div className="header-actions"><button className="secondary-button" disabled={!selectedTask || !leadsQuery.data?.total} onClick={() => { setTopN(leadsQuery.data?.total ?? 1); setShowExport(true); }}><FileSpreadsheet size={16} />导出</button></div></div>
        {selectedTask ? <LeadTable data={leadsQuery.data} filters={filters} visible={visible} onFilters={(value) => { setFilters(value); setPage(1); }} onVisible={setVisible} onPage={setPage} onSort={changeSort} onSelect={(lead) => setSelectedLead(lead.enterprise_id)} /> : <div className="empty-panel"><UsersRound size={28} /><strong>选择或创建任务</strong><span>完成后将在这里显示版本绑定的潜客结果</span></div>}
        <section className="history-section"><div className="section-heading"><h3>导出记录</h3><span>{exportsQuery.data?.count ?? 0}</span></div><ExportHistory items={exportsQuery.data?.items ?? []} /></section>
      </section>
    </main>
    {selectedLead && <LeadDetailDrawer detail={detailQuery.data} loading={detailQuery.isLoading} onClose={() => setSelectedLead(undefined)} />}
    {showExport && selectedTask && <ExportPanel fields={fieldsQuery.data?.items ?? []} selected={exportFields} topN={topN} maxRows={leadsQuery.data?.total ?? 1} options={exportOptions} job={exportMutation.data} error={exportMutation.error?.message} busy={exportMutation.isPending} onSelected={setExportFields} onTopN={setTopN} onOptions={setExportOptions} onSubmit={() => exportMutation.mutate()} onClose={() => { setShowExport(false); exportMutation.reset(); }} />}
  </div>;
}
