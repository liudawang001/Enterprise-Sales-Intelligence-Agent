export type VerificationStatus = "VERIFIED" | "PARTIAL" | "CONFLICTING" | "UNVERIFIED" | "MISSING";

export interface DeliveryLead {
  rank: number;
  enterprise_id: string;
  enterprise_name: string;
  parent_enterprise: string | null;
  industry: string | null;
  company_scale: string | null;
  region: string | null;
  office_count: number | null;
  office_address: string | null;
  public_phone: string | null;
  website: string | null;
  recommended_business: string;
  lead_score: number | null;
  score_status: string;
  verification_status: VerificationStatus;
  evidence_confidence: number | null;
  recommendation_reason: string | null;
  primary_source: string | null;
  primary_source_url: string | null;
  verified_at: string | null;
  field_statuses: Record<string, VerificationStatus>;
}

export interface LeadPage {
  snapshot_id: string;
  task_id: string;
  task_version: number;
  score_set_id: string;
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  sort_by: string;
  sort_order: string;
  view_sort: boolean;
  items: DeliveryLead[];
  quality_summary: Record<string, number>;
}

export interface ScoreExplain {
  enterprise_id: string;
  lead_score_id: string;
  total_score: number | null;
  rank_status: string;
  verification_status: string;
  evidence_coverage: number;
  scoring_profile_id: string;
  scoring_profile_version: number;
  components: Array<{
    component: string;
    raw_score: number;
    weighted_score: number;
    weight: number;
    reason_codes: string[];
    evidence_ids: string[];
  }>;
  recommendation_reason: string | null;
  reason_codes: string[];
  evidence_ids: string[];
}

export interface LeadDetail {
  snapshot_id: string;
  task_id: string;
  task_version: number;
  score_set_id: string;
  lead: DeliveryLead;
  enterprise_profile: Record<string, unknown>;
  relations: Record<string, unknown>[];
  locations: Record<string, unknown>[];
  resolved_fields: Array<{
    resolved_field_id: string;
    enterprise_id: string;
    field_name: string;
    primary_value: unknown;
    status: VerificationStatus;
    confidence: number;
    supporting_evidence_ids: string[];
    conflicting_evidence_ids: string[];
    alternatives: unknown[];
  }>;
  score: ScoreExplain;
  evidence: import("./evidence").Evidence[];
}
