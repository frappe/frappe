/** One Client Script row: a `Client Script` with `view = Record`, as `get_client_scripts` returns it. */
export interface ClientScriptRow {
  name: string;
  script: string;
}

export interface ClientScriptsResponse {
  scripts: ClientScriptRow[];
  /** Whether this user may write Client Scripts — the gate on failure toasts. */
  can_write: boolean;
}

export const CLIENT_SCRIPT_CHANGED = "client_script_changed";
export const GET_CLIENT_SCRIPTS =
  "frappe.custom.doctype.client_script.client_script.get_client_scripts";
