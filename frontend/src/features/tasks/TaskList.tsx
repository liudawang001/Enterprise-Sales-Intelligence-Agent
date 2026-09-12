import { Building2, Check, CircleDot } from "lucide-react";
import type { TaskSummary } from "../../types/task";
import { StatusBadge } from "../../components/StatusBadge";

export function TaskList({ tasks, selectedId, onSelect }: { tasks: TaskSummary[]; selectedId?: string; onSelect: (task: TaskSummary) => void }) {
  return <nav className="task-list" aria-label="营销任务">
    {tasks.length === 0 ? <div className="empty-panel"><Building2 size={24} /><strong>暂无营销任务</strong><span>在对话区输入业务、地区和目标数量</span></div> : tasks.map((task) => <button className={task.task_id === selectedId ? "task-item selected" : "task-item"} key={task.task_id} onClick={() => onSelect(task)}>
      <span className="task-item-head"><strong>{task.business ?? "待补充业务"}</strong>{task.active ? <Check size={14} aria-label="当前任务" /> : <CircleDot size={13} />}</span>
      <span>{task.region ?? "地区待补充"} · Top {task.target_count ?? "?"}</span>
      <span className="task-item-foot"><StatusBadge value={task.status} /><time>{new Date(task.updated_at).toLocaleDateString("zh-CN")}</time></span>
    </button>)}
  </nav>;
}
