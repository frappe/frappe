import { call } from "frappe-ui";
import type { SavedViewState } from "./savedView";
import type { SavedView } from "./types";

const ENDPOINT = "frappe.desk.doctype.saved_view.api.";

export const savedViewApi = {
  create(params: {
    doctype: string;
    label: string;
    app: string;
    icon?: string;
    shared?: boolean;
    state?: SavedViewState;
    section?: string | null;
  }): Promise<ViewName> {
    return call(ENDPOINT + "create_view", {
      reference_doctype: params.doctype,
      label: params.label,
      app: params.app,
      icon: params.icon,
      shared: Boolean(params.shared),
      section: params.section ?? undefined,
      ...params.state,
    });
  },

  saveState(view: ViewName, state: SavedViewState): Promise<ViewName> {
    return call(ENDPOINT + "save_view_state", { view, ...state });
  },

  getLanding(doctype: string): Promise<SavedView | null> {
    return call(ENDPOINT + "get_landing_view", { reference_doctype: doctype });
  },

  saveLanding(doctype: string, state: SavedViewState): Promise<ViewName> {
    return call(ENDPOINT + "save_landing_state", {
      reference_doctype: doctype,
      ...state,
    });
  },

  update(view: ViewName, changes: { label?: string; icon?: string }) {
    return call("frappe.client.set_value", {
      doctype: "Saved View",
      name: view,
      fieldname: changes,
    });
  },

  duplicate(view: ViewName, app: string): Promise<ViewName> {
    return call(ENDPOINT + "duplicate_view", { view, app });
  },

  setAsDefault(view: ViewName): Promise<ViewName> {
    return call(ENDPOINT + "set_as_default", { view });
  },

  deleteView(view: ViewName): Promise<ViewName> {
    return call(ENDPOINT + "delete_view", { view });
  },

  move(view: ViewName, shared: boolean, app: string): Promise<ViewName> {
    return call(ENDPOINT + "move_view", { view, shared, app });
  },
};

export type ViewName = string | number;
