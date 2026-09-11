import { AlertTriangle, CheckCircle2, CircleHelp, Clock3 } from "lucide-react";

const config: Record<string, { label: string; className: string; Icon: typeof CheckCircle2 }> = {
  VERIFIED: { label: "已核验", className: "status verified", Icon: CheckCircle2 },
  PARTIAL: { label: "部分核验", className: "status partial", Icon: Clock3 },
  CONFLICTING: { label: "存在冲突", className: "status conflicting", Icon: AlertTriangle },
  UNVERIFIED: { label: "未核验", className: "status unverified", Icon: CircleHelp },
  MISSING: { label: "缺失", className: "status unverified", Icon: CircleHelp },
  COMPLETED: { label: "已完成", className: "status verified", Icon: CheckCircle2 },
  RUNNING: { label: "执行中", className: "status running", Icon: Clock3 },
  FAILED: { label: "失败", className: "status conflicting", Icon: AlertTriangle }
};

export function StatusBadge({ value }: { value: string }) {
  const item = config[value] ?? { label: value, className: "status unverified", Icon: CircleHelp };
  return <span className={item.className}><item.Icon size={13} aria-hidden />{item.label}</span>;
}
