export type TaskStatus = "RUNNING" | "WAITING_USER" | "COMPLETED" | "FAILED";

export interface TaskSummary {
  task_id: string;
  session_id: string;
  business: string | null;
  region: string | null;
  target_count: number | null;
  status: TaskStatus;
  stage: string;
  active: boolean;
  current_version: number;
  viewed_version: number;
  historical: boolean;
  result_count: number;
  updated_at: string;
  criteria_snapshot_id: string | null;
  verified_lead_set_id: string | null;
  lead_score_set_id: string | null;
  current_mutation_scope: string | null;
  hard_constraints: Record<string, unknown>[];
  soft_preferences: Record<string, unknown>[];
}

export interface TaskVersion {
  task_id: string;
  version: number;
  parent_version: number | null;
  business: string | null;
  region: string | null;
  target_count: number | null;
  constraints: Record<string, unknown>[];
  required_fields: string[];
  export_fields: string[];
  read_only: boolean;
  created_at: string;
}

export interface InterruptPayload {
  type: "CLARIFICATION_REQUIRED" | "RULE_CONFLICT" | "TASK_SELECTION_REQUIRED";
  question: string;
  missing_slots: string[];
  conflicts: Record<string, unknown>[];
  candidate_tasks: Array<{ task_id: string; business?: string; region?: string; version: number }>;
}

export interface ChatResponse {
  status: "COMPLETED" | "WAITING_USER";
  task_id: string | null;
  message?: string;
  interrupt?: InterruptPayload;
  data?: {
    export_id?: string;
    warnings?: string[];
    mutation_id?: string;
    reexecution_plan_id?: string;
  };
}
