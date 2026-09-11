import { useEffect, useState } from "react";
import { getTaskStatus } from "../api/tasks";

export interface TaskProgress {
  event: string;
  stage: string;
  status: string;
}

export function useTaskEvents(taskId?: string) {
  const [progress, setProgress] = useState<TaskProgress>();
  useEffect(() => {
    if (!taskId) return;
    let active = true;
    const recover = () => getTaskStatus(taskId).then((value) => {
      if (active) setProgress({ event: value.progress.event, stage: value.stage, status: value.status });
    }).catch(() => undefined);
    recover();
    const source = new EventSource(`/api/tasks/${taskId}/events/stream`);
    source.onmessage = (event) => {
      const value = JSON.parse(event.data) as TaskProgress;
      if (active) setProgress(value);
    };
    source.onerror = () => {
      source.close();
      recover();
    };
    return () => { active = false; source.close(); };
  }, [taskId]);
  return progress;
}
