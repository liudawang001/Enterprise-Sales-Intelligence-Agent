import { AlertTriangle, ListChecks, MessageSquareMore } from "lucide-react";
import type { InterruptPayload } from "../types/task";

export function InterruptCard({ interrupt, onSubmit }: { interrupt: InterruptPayload; onSubmit: (value: string) => void }) {
  const Icon = interrupt.type === "RULE_CONFLICT" ? AlertTriangle : interrupt.type === "TASK_SELECTION_REQUIRED" ? ListChecks : MessageSquareMore;
  return <section className="interrupt" aria-label={interrupt.type}>
    <div className="interrupt-title"><Icon size={18} /><strong>{interrupt.question || "需要补充信息"}</strong></div>
    {interrupt.type === "TASK_SELECTION_REQUIRED" ? <div className="task-options">
      {interrupt.candidate_tasks.map((task) => <button key={task.task_id} onClick={() => onSubmit(task.task_id)}>
        <span>{task.business ?? "未命名任务"}</span><small>{task.region ?? "未指定地区"} · v{task.version}</small>
      </button>)}
    </div> : <form onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); onSubmit(String(data.get("answer") ?? "")); }}>
      <input name="answer" aria-label="补充信息" placeholder={interrupt.missing_slots.join("、") || "输入调整后的条件"} required />
      <button type="submit">继续</button>
    </form>}
  </section>;
}
