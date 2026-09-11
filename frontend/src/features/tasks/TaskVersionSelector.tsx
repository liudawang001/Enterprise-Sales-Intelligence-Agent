import { History } from "lucide-react";
import type { TaskVersion } from "../../types/task";

export function TaskVersionSelector({ versions, value, current, onChange }: { versions: TaskVersion[]; value: number; current: number; onChange: (version: number) => void }) {
  return <label className="version-control"><History size={15} /><span className="sr-only">任务版本</span>
    <select aria-label="任务版本" value={value} onChange={(event) => onChange(Number(event.target.value))}>
      {versions.slice().reverse().map((item) => <option key={item.version} value={item.version}>v{item.version}{item.version === current ? " 当前" : " 历史"}</option>)}
    </select>
  </label>;
}
