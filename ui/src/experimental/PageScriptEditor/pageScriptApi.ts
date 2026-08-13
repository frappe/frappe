// Page Script CRUD for the editor. The runtime tier has its own whitelisted
// read (`get_page_scripts`) which returns only *enabled* scripts and only the
// text; the editor needs the disabled ones and the `enabled` flag too, so it
// goes through the standard document API — which is also where the doctype's
// permissions (System Manager by default) do the gating.
import { call } from "frappe-ui";

export const PAGE_SCRIPT_DOCTYPE = "Page Script";

/** Every stored field, so a whole-doc save never blanks one it left out. */
const FIELDS = [
  "name",
  "dt",
  "view",
  "enabled",
  "module",
  "script",
  "run_order",
  "modified",
];

/** Scripts run low to high; `creation` breaks the ties, so 0 means "unpositioned". */
const RUN_ORDER = "run_order asc, creation asc";

export interface PageScriptDoc {
  name: string;
  dt: string;
  view: string;
  enabled: 0 | 1;
  module: string | null;
  script: string;
  /** Position within this doctype's list. A pure sort key -- ties are legal. */
  run_order: number;
  /** The optimistic-lock token; a stale one makes `save` throw. */
  modified: string;
}

export const pageScriptApi = {
  /** Every script for the doctype, disabled ones included, in run order. */
  list(dt: string, view = "Record"): Promise<PageScriptDoc[]> {
    return call("frappe.client.get_list", {
      doctype: PAGE_SCRIPT_DOCTYPE,
      filters: { dt, view },
      fields: FIELDS,
      order_by: RUN_ORDER,
      limit_page_length: 0,
    });
  },

  // `autoname: prompt` — the author types the name, and it is the name that
  // shows up in stack traces as `page-script/<name>.js`. A new script omits
  // `script` so the doctype's own default is the one prefilled; a duplicate
  // passes the body it is copying, and `enabled: 0` so it cannot start running
  // beside its original before anyone has looked at it.
  create(doc: {
    name: string;
    dt: string;
    view?: string;
    script?: string;
    enabled?: 0 | 1;
    run_order?: number;
  }): Promise<PageScriptDoc> {
    return call("frappe.client.insert", {
      doc: {
        doctype: PAGE_SCRIPT_DOCTYPE,
        name: doc.name,
        dt: doc.dt,
        view: doc.view ?? "Record",
        ...(doc.script === undefined ? {} : { script: doc.script }),
        ...(doc.enabled === undefined ? {} : { enabled: doc.enabled }),
        ...(doc.run_order === undefined ? {} : { run_order: doc.run_order }),
      },
    });
  },

  /**
   * Writes the edited fields onto the server's current document, but carrying
   * the `modified` the editor loaded — so a script another author saved in the
   * meantime is refused instead of silently overwritten.
   *
   * Not `set_value`, which strips `modified` before re-reading the document, so
   * its `check_if_latest` can never fire; and not a document assembled here,
   * which a `set_only_once` field the editor does not carry (`creation`) rejects.
   */
  async save(doc: PageScriptDoc): Promise<PageScriptDoc> {
    const current = await call("frappe.client.get", {
      doctype: PAGE_SCRIPT_DOCTYPE,
      name: doc.name,
    });
    return call("frappe.client.save", {
      doc: {
        ...current,
        script: doc.script,
        enabled: doc.enabled,
        modified: doc.modified,
      },
    });
  },

  /**
   * Renumbers the whole list 1..n in one transaction, rather than one save per
   * script: N separate saves can tear halfway and leave the list numbered
   * 1,2,3,3,4. Server-side it also collapses N realtime broadcasts into one.
   *
   * Order belongs to the list, not to any one script, so this is not part of the
   * editor's per-script dirty buffer -- a drop calls it straight away.
   */
  reorder(dt: string, names: string[], view = "Record"): Promise<unknown> {
    return call("frappe.desk.doctype.page_script.page_script.reorder", {
      dt,
      view,
      names,
    });
  },

  remove(name: string): Promise<unknown> {
    return call("frappe.client.delete", {
      doctype: PAGE_SCRIPT_DOCTYPE,
      name,
    });
  },
};
