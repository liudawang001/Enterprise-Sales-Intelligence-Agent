import { Check, LoaderCircle } from "lucide-react";

const STAGES = ["任务建立", "业务规则", "企业发现", "信息补全", "证据核验", "潜客评分", "结果交付"];

export function ProgressTimeline({ stage, completed }: { stage: string; completed: boolean }) {
  const stageIndex = Math.max(0, ["CREATED", "BUSINESS_PLANNING", "DISCOVERY", "CHEAP_ENRICHMENT", "VERIFICATION", "SCORING", "COMPLETED"].indexOf(stage));
  return (
    <ol className="timeline" aria-label="任务进度" tabIndex={0}>
      {STAGES.map((label, index) => {
        const done = completed || index < stageIndex;
        const active = !completed && index === stageIndex;
        return <li key={label} className={active ? "active" : done ? "done" : ""}>
          <span className="timeline-dot">{done ? <Check size={12} /> : active ? <LoaderCircle size={12} className="spin" /> : null}</span>
          <span>{label}</span>
        </li>;
      })}
    </ol>
  );
}
