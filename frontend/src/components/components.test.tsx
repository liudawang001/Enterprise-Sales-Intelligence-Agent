import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { EvidenceTable } from "./EvidenceTable";
import { InterruptCard } from "./InterruptCard";
import { ProgressTimeline } from "./ProgressTimeline";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { StatusBadge } from "./StatusBadge";
import { LeadDetailDrawer } from "../features/leads/LeadDetailDrawer";
import { LeadTable } from "../features/leads/LeadTable";
import { TaskList } from "../features/tasks/TaskList";
import { TaskVersionSelector } from "../features/tasks/TaskVersionSelector";
import { ExportPanel } from "../features/exports/ExportPanel";
import { detail, evidence, leadPage, score, task, versions } from "../test/fixtures";

test("status, task list, versions and progress preserve semantic text", () => {
  const onSelect = vi.fn();
  const onVersion = vi.fn();
  render(<><StatusBadge value="CONFLICTING" /><TaskList tasks={[task]} selectedId={task.task_id} onSelect={onSelect} /><TaskVersionSelector versions={versions} value={3} current={5} onChange={onVersion} /><ProgressTimeline stage="VERIFICATION" completed={false} /></>);
  expect(screen.getByText("存在冲突")).toBeInTheDocument();
  fireEvent.click(screen.getByText("集团V网"));
  expect(onSelect).toHaveBeenCalledWith(task);
  fireEvent.change(screen.getByLabelText("任务版本"), { target: { value: "5" } });
  expect(onVersion).toHaveBeenCalledWith(5);
  expect(screen.getByText("证据核验")).toBeInTheDocument();
});

test("lead table uses server page ranks and opens details", () => {
  const onSelect = vi.fn();
  render(<LeadTable data={leadPage} filters={{ verification_status: "", min_score: "", industry: "", has_public_phone: "", has_website: "" }} visible={new Set(["industry", "website"])} onFilters={vi.fn()} onVisible={vi.fn()} onPage={vi.fn()} onSort={vi.fn()} onSelect={onSelect} />);
  expect(screen.getByText("上海示例科技有限公司")).toBeInTheDocument();
  expect(screen.getByText("88.0")).toBeInTheDocument();
  fireEvent.click(screen.getByText("上海示例科技有限公司"));
  expect(onSelect).toHaveBeenCalled();
});

test("lead drawer exposes score, field status and evidence source", () => {
  render(<LeadDetailDrawer detail={detail} loading={false} onClose={vi.fn()} />);
  expect(screen.getByRole("dialog", { name: "潜客详情" })).toBeInTheDocument();
  expect(screen.getByText("推荐理由")).toBeInTheDocument();
  expect(screen.getByText("业务匹配")).toBeInTheDocument();
  expect(screen.getByText("OFFICIAL_WEBSITE · official")).toBeInTheDocument();
  expect(screen.getAllByText("存在冲突").length).toBeGreaterThan(0);
});

test("evidence, score and interrupt controls keep structured behavior", () => {
  const submit = vi.fn();
  const { rerender } = render(<InterruptCard interrupt={{ type: "CLARIFICATION_REQUIRED", question: "请选择地区", missing_slots: ["region"], conflicts: [], candidate_tasks: [] }} onSubmit={submit} />);
  fireEvent.change(screen.getByLabelText("补充信息"), { target: { value: "上海松江" } });
  fireEvent.click(screen.getByText("继续"));
  expect(submit).toHaveBeenCalledWith("上海松江");
  rerender(<InterruptCard interrupt={{ type: "RULE_CONFLICT", question: "规则冲突", missing_slots: [], conflicts: [{ field: "industry" }], candidate_tasks: [] }} onSubmit={submit} />);
  expect(screen.getByLabelText("RULE_CONFLICT")).toBeInTheDocument();
  rerender(<InterruptCard interrupt={{ type: "TASK_SELECTION_REQUIRED", question: "请选择任务", missing_slots: [], conflicts: [], candidate_tasks: [{ task_id: "task-2", business: "企业专线", region: "上海浦东", version: 2 }] }} onSubmit={submit} />);
  fireEvent.click(screen.getByText("企业专线"));
  expect(submit).toHaveBeenCalledWith("task-2");
  rerender(<><EvidenceTable evidence={[evidence]} /><ScoreBreakdown score={score} /></>);
  expect(screen.getByRole("link", { name: /来源/ })).toHaveAttribute("rel", "noopener noreferrer");
  expect(screen.getByText("18.0")).toBeInTheDocument();
});

test("export panel submits exact field and sheet choices", () => {
  const submit = vi.fn();
  render(<ExportPanel fields={[{ field_key: "enterprise_name", display_name: "企业名称", source_path: "enterprise_name", data_type: "TEXT", default_visible: true, exportable: true, sensitive: false }]} selected={new Set(["enterprise_name"])} topN={1} maxRows={1} options={{ score: true, evidence: true, conflicts: true, task: true }} busy={false} onSelected={vi.fn()} onTopN={vi.fn()} onOptions={vi.fn()} onSubmit={submit} onClose={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "生成 XLSX" }));
  expect(submit).toHaveBeenCalledOnce();
});
