import { api, queryString } from "./client";
import type { LeadDetail, LeadPage } from "../types/lead";

export interface LeadQuery {
  page: number;
  page_size: number;
  sort_by: string;
  sort_order: string;
  verification_status?: string;
  min_score?: number;
  industry?: string;
  has_public_phone?: boolean;
  has_website?: boolean;
}

export const getLeads = (taskId: string, version: number, query: LeadQuery) => api<LeadPage>(`/api/tasks/${taskId}/versions/${version}/leads${queryString(query)}`);
export const getLead = (taskId: string, version: number, enterpriseId: string) => api<LeadDetail>(`/api/tasks/${taskId}/versions/${version}/leads/${enterpriseId}`);
