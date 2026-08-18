interface InputLabelingProps {
  label?: string;
  description?: string;
  required?: boolean;
}

export interface TableMultiSelectProps extends InputLabelingProps {
  /** Doctype the links point at — the picker searches its records. */
  doctype: string;
  /** Link search filters, forwarded to `search_link`. */
  filters?: Record<string, unknown>;
  placeholder?: string;
  disabled?: boolean;
  /**
   * Show a "Create '{query}'" action in the footer when the user has typed a
   * query. The control does **not** create anything itself — it emits `create`
   * and the host wires the behaviour (open quick-entry, insert, …), exactly like
   * `Link`'s `creatable` + `@create`.
   */
  creatable?: boolean;
}

export type TableMultiSelectEmits = {
  /** Fired when the footer "Create" action is clicked, with the typed query. */
  create: [query: string];
};

export type TableMultiSelectOption = {
  label: string;
  value: string;
};
