import { useEffect, useState } from "react";
import { getTaskStatus } from "../api/tasks";

const TASK_EVENT_TYPES = [
  "TASK_PROGRESS", "TASK_STATUS", "FINAL", "CLARIFICATION_REQUIRED", "TASK_SELECTION_REQUIRED",
  "RESEARCH_PROGRESS", "RESEARCH_COMPLETED", "EXPORT_COMPLETED", "EXPORT_FAILED", "ARTIFACT_REUSED",
  "FILTER_REEXECUTION_COMPLETED", "TARGETED_ENRICHMENT_COMPLETED", "ARTIFACT_PROMOTION_REJECTED",
  "TASK_MUTATION_PARSED", "TASK_DIFF_READY", "INVALIDATION_CLASSIFIED", "REEXECUTION_PLANNED",
  "REEXECUTION_STARTED",
];

export interface TaskProgress {
  event: string;
  stage: string;
  status: string;
  connection?: "connected" | "reconnecting" | "closed";
}

export function useTaskEvents(taskId?: string) {
  const [progress, setProgress] = useState<TaskProgress>();
  useEffect(() => {
    if (!taskId) return;
    let active = true;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let lastEventId = "";
    let source: EventSource;
    const recover = () => getTaskStatus(taskId).then((value) => {
      if (active) setProgress({ event: value.progress.event, stage: value.stage, status: value.status });
    }).catch(() => undefined);
    recover();
    const connect = () => {
      const suffix = lastEventId ? `?last_event_id=${encodeURIComponent(lastEventId)}` : "";
      source = new EventSource(`/api/tasks/${taskId}/events/stream${suffix}`, { withCredentials: true });
      const onEvent = (event: MessageEvent<string>) => {
        lastEventId = event.lastEventId || lastEventId;
        const value = JSON.parse(event.data) as TaskProgress;
        if (active) setProgress({ ...value, connection: "connected" });
      };
      source.onopen = () => setProgress((value) => value ? { ...value, connection: "connected" } : value);
      source.onmessage = onEvent;
      if (typeof source.addEventListener === "function") {
        TASK_EVENT_TYPES.forEach((type) => source.addEventListener(type, onEvent));
      }
      source.onerror = () => {
        source.close();
        if (active) {
          setProgress((value) => value ? { ...value, connection: "reconnecting" } : value);
          recover();
          retryTimer = setTimeout(connect, 1000);
        }
      };
    };
    connect();
    return () => {
      active = false;
      if (retryTimer) clearTimeout(retryTimer);
      source.close();
    };
  }, [taskId]);
  return progress;
}
