import { api } from "./client";
import type { ChatResponse, TaskSummary, TaskVersion } from "../types/task";

export const getTasks = (sessionId?: string) => api<TaskSummary[]>(`/api/tasks${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`);
export const getTask = (taskId: string) => api<{ task: Record<string, unknown>; summary: TaskSummary }>(`/api/tasks/${taskId}`);
export const getTaskVersions = (taskId: string) => api<TaskVersion[]>(`/api/tasks/${taskId}/versions`);
export const activateTask = (taskId: string, sessionId: string) => api<{ task_id: string; active: boolean; version: number }>(`/api/tasks/${taskId}/activate`, { method: "POST", body: JSON.stringify({ session_id: sessionId }) });
export const sendChat = (sessionId: string, message: string) => api<ChatResponse>("/api/chat", { method: "POST", body: JSON.stringify({ session_id: sessionId, message }) });
export const getTaskStatus = (taskId: string) => api<{ task_id: string; task_version: number; stage: string; status: string; progress: { event: string; stage: string } }>(`/api/tasks/${taskId}/events`);
