import type { Evidence } from "../types/evidence";
import type { DeliveryLead, LeadDetail, LeadPage, ScoreExplain } from "../types/lead";
import type { TaskSummary, TaskVersion } from "../types/task";

export const task: TaskSummary = {
  task_id: "task-1", session_id: "session-1", business: "集团V网", region: "上海松江", target_count: 30,
  status: "COMPLETED", stage: "COMPLETED", active: true, current_version: 5, viewed_version: 5,
  historical: false, result_count: 1, updated_at: "2026-09-11T10:00:00Z", criteria_snapshot_id: "criteria-1",
  verified_lead_set_id: "lead-set-1", lead_score_set_id: "score-set-1", current_mutation_scope: "FILTER_ONLY",
  hard_constraints: [], soft_preferences: []
};

export const versions: TaskVersion[] = [3, 5].map((version) => ({
  task_id: task.task_id, version, parent_version: version === 3 ? 2 : 4, business: task.business, region: task.region,
  target_count: task.target_count, constraints: [], required_fields: [], export_fields: [], read_only: version !== 5,
  created_at: "2026-09-11T10:00:00Z"
}));

export const lead: DeliveryLead = {
  rank: 1, enterprise_id: "enterprise-1", enterprise_name: "上海示例科技有限公司", parent_enterprise: null,
  industry: "科技", company_scale: "中型", region: "上海松江", office_count: 3, office_address: "松江区示例路1号",
  public_phone: "021-55550000", website: "https://example.com", recommended_business: "集团V网", lead_score: 88,
  score_status: "SCORED", verification_status: "CONFLICTING", evidence_confidence: .82,
  recommendation_reason: "办公分布与业务条件匹配，公开电话存在来源冲突。", primary_source: "OFFICIAL_WEBSITE",
  primary_source_url: "https://example.com/contact", verified_at: "2026-09-11T10:00:00Z",
  field_statuses: { public_phone: "CONFLICTING", website: "VERIFIED" }
};

export const evidence: Evidence = {
  evidence_id: "evidence-1", enterprise_id: lead.enterprise_id, field_name: "public_phone", value: lead.public_phone,
  normalized_value: lead.public_phone, verification_role: "CONFLICTING", provider: "official", source_type: "OFFICIAL_WEBSITE",
  source_record_id: "source-1", source_url: "https://example.com/contact", retrieved_at: "2026-09-11T09:00:00Z", confidence: .9
};

export const score: ScoreExplain = {
  enterprise_id: lead.enterprise_id, lead_score_id: "lead-score-1", total_score: 88, rank_status: "SCORED",
  verification_status: "CONFLICTING", evidence_coverage: .82, scoring_profile_id: "profile-1", scoring_profile_version: 1,
  components: [{ component: "business_fit", raw_score: .9, weighted_score: 18, weight: 20, reason_codes: ["MATCH"], evidence_ids: [evidence.evidence_id] }],
  recommendation_reason: lead.recommendation_reason, reason_codes: ["MATCH"], evidence_ids: [evidence.evidence_id]
};

export const detail: LeadDetail = {
  snapshot_id: "snapshot-1", task_id: task.task_id, task_version: 5, score_set_id: "score-set-1", lead,
  enterprise_profile: { enterprise_id: lead.enterprise_id }, relations: [], locations: [{ address: lead.office_address }],
  resolved_fields: [{ resolved_field_id: "field-1", enterprise_id: lead.enterprise_id, field_name: "public_phone", primary_value: lead.public_phone, status: "CONFLICTING", confidence: .9, supporting_evidence_ids: [], conflicting_evidence_ids: [evidence.evidence_id], alternatives: ["021-55551111"] }],
  score, evidence: [evidence]
};

export const leadPage: LeadPage = {
  snapshot_id: "snapshot-1", task_id: task.task_id, task_version: 5, score_set_id: "score-set-1", page: 1, page_size: 20,
  total: 1, total_pages: 1, sort_by: "rank", sort_order: "asc", view_sort: false, items: [lead],
  quality_summary: { VERIFIED: 0, PARTIAL: 0, CONFLICTING: 1, UNVERIFIED: 0, evidence_coverage: .82, contact_completeness: 1 }
};
