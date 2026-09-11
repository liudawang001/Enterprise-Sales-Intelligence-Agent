import { api } from "./client";
import type { ExportField, ExportJob } from "../types/export";

export const getExportFields = () => api<{ items: ExportField[] }>("/api/exports/fields");
export const createExport = (payload: { task_id: string; task_version: number; snapshot_id?: string; target_count?: number; fields: string[]; include_task_summary: boolean; include_score_breakdown: boolean; include_evidence_summary: boolean; include_conflicts: boolean }) => api<ExportJob>("/api/exports", { method: "POST", body: JSON.stringify(payload) });
export const getExports = (taskId: string) => api<{ items: ExportJob[]; count: number }>(`/api/tasks/${taskId}/exports`);
export const exportDownloadUrl = (exportId: string) => `/api/exports/${exportId}/download`;
