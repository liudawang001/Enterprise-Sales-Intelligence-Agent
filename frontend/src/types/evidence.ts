export interface Evidence {
  evidence_id: string;
  enterprise_id: string;
  field_name: string;
  value: unknown;
  normalized_value: unknown;
  verification_role: "SUPPORTING" | "CONFLICTING";
  provider: string;
  source_type: string;
  source_record_id: string;
  source_url: string | null;
  retrieved_at: string;
  confidence: number;
}
