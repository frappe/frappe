export type DataImportStatus =
  | "Pending"
  | "In Progress"
  | "Success"
  | "Partial Success"
  | "Error"
  | "Timed Out";

export type DataImportType =
  | "Insert New Records"
  | "Update Existing Records"
  | "Insert or Update Records";

/** A source value in the file that matches no Link or Select option. */
export interface DataImportValueMapping {
  name?: string;
  column_label?: string;
  source_value: string;
  no_of_rows?: string;
  /** JSON list of sheet row numbers */
  row_numbers?: string;
  target_value?: string | null;
  column: number;
  fieldname: string;
  parent_field?: string;
  fieldtype: "Select" | "Link";
  link_doctype?: string;
  select_options?: string;
  /** Set by the server when a record can be made from the file's value alone. */
  can_create?: 0 | 1;
  /** Create the record, named after the file's value, when the import runs. */
  create_new?: 0 | 1;
}

export interface DataImportSkippedRow {
  name?: string;
  row_number: number;
  /** JSON of the row's cells */
  row_data: string;
}

/** The full Data Import document, child tables included. */
export interface DataImportDoc {
  doctype: "Data Import";
  name?: string;
  reference_doctype: string;
  import_type: DataImportType;
  status: DataImportStatus;
  import_file?: string | null;
  google_sheets_url?: string | null;
  mute_emails: 0 | 1;
  submit_after_import: 0 | 1;
  use_csv_sniffer: 0 | 1;
  custom_delimiters: 0 | 1;
  delimiter_options?: string | null;
  payload_count?: number;
  /** JSON, kept by the preview's column picker */
  template_options?: string | null;
  /** JSON list of warnings saved by a blocked import */
  template_warnings?: string | null;
  /** JSON, kept by the tree preview */
  tree_parent_overrides?: string | null;
  value_mappings: DataImportValueMapping[];
  skipped_rows: DataImportSkippedRow[];
  owner?: string;
  creation?: string;
  modified_by?: string;
  modified?: string;
}

/** `get_preview_from_template`; at most 10 rows of `data` come back. */
export interface DataImportPreview {
  columns: Record<string, any>[];
  data: unknown[][];
  warnings: Record<string, any>[];
  import_log: { row_indexes: string; success: 0 | 1 }[];
  total_number_of_rows: number;
  max_rows_exceeded?: boolean;
  max_rows_in_preview?: number;
  /** cells of warned rows that fall past the preview's first rows */
  warning_rows?: unknown[][];
  tree_preview?: Record<string, any>;
}

/** `get_import_status` */
export interface DataImportStatusSummary {
  status: DataImportStatus;
  total_records?: number;
  processed_records?: number;
  success?: number;
  failed?: number;
  /** only for "Insert or Update Records" */
  inserted?: number;
  updated?: number;
}

export type DataImportLogFilter = "all" | "success" | "failed";

/** A row of `get_import_logs` (the server sends at most 1000). */
export interface DataImportLog {
  success: 0 | 1;
  docname?: string | null;
  /** JSON */
  messages?: string | null;
  exception?: string | null;
  /** JSON list of sheet row numbers */
  row_indexes?: string | null;
  import_action?: "Insert" | "Update" | null;
}

export interface DataImportActivity {
  kind: string;
  text: string;
  isHtml: boolean;
  row: number | null;
}

/** Live progress of a running import, built from `data_import_progress` events. */
export interface DataImportProgress {
  current: number;
  total: number;
  /** seconds left */
  eta: number;
  inserted: number;
  updated: number;
  failed: number;
  skipping: boolean;
  /** newest first, at most 5 */
  recentActivity: DataImportActivity[];
}

/** A provider's own field list, used instead of the DocType's meta when set. */
export interface ImportProviderSchema {
  fields: Record<string, any>[];
  child_tables?: {
    fieldname: string;
    label: string;
    fields: Record<string, any>[];
  }[];
}

export interface DocField {
  label: string;
  fieldname: string;
  reqd: 0 | 1;
  fieldtype: string;
  options?: string;
  parent?: string;
  depends_on?: string;
  is_virtual?: 0 | 1;
  in_import_template?: 0 | 1;
}

export interface DocType {
  name: string;
  fields: DocField[];
  autoname?: string;
  is_submittable?: 0 | 1;
}
