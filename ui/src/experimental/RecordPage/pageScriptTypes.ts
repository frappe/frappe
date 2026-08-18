/** One Page Script row as `get_page_scripts` returns it. */
export interface PageScriptRow {
  name: string;
  script: string;
}

export interface PageScriptsResponse {
  scripts: PageScriptRow[];
  /** Whether this user may write Page Scripts — the gate on failure toasts. */
  can_write: boolean;
}

export const PAGE_SCRIPT_CHANGED = "page_script_changed";
export const GET_PAGE_SCRIPTS =
  "frappe.desk.doctype.page_script.page_script.get_page_scripts";
