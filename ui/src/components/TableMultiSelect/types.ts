import type { LinkExposed } from "../Link/types";

interface InputLabelingProps {
  label?: string;
  description?: string;
  required?: boolean;
}

export interface TableMultiSelectProps extends InputLabelingProps {
  /** Doctype the links point at — the picker searches its records. */
  doctype: string;
  /** Link search filters, forwarded to the search. */
  filters?: Record<string, unknown>;
  placeholder?: string;
  disabled?: boolean;
  /**
   * Show a Create action in the footer. The control does **not** create anything
   * itself — it emits `create` and closes, and the host wires the behaviour,
   * exactly like `Link`'s `creatable` + `@create`.
   */
  creatable?: boolean;
  /** What selected values display as until the search returns them. */
  titles?: Record<string, string>;
}

export type TableMultiSelectEmits = {
  /** Fired when the footer "Create" action is clicked, with the typed query. */
  create: [query: string];
};

export interface TableMultiSelectSlots {
  /** The footer Create action's label; receives the typed query. */
  create?: (props: { query: string }) => any;
}

export type TableMultiSelectExposed = Pick<LinkExposed, "search" | "focus">;

export type TableMultiSelectOption = {
  label: string;
  value: string;
};
