export interface ExportField {
  field_key: string;
  display_name: string;
  source_path: string;
  data_type: string;
  default_visible: boolean;
  exportable: boolean;
  sensitive: boolean;
}

export interface ExportJob {
  export_id: string;
  snapshot_id: string;
  task_id: string;
  task_version: number;
  status: "PENDING" | "GENERATING" | "COMPLETED" | "FAILED";
  requested_fields: string[];
  row_count: number | null;
  file_name: string | null;
  file_size: number | null;
  sha256: string | null;
  created_at: string;
  completed_at: string | null;
  error_code: string | null;
  error_message: string | null;
}
