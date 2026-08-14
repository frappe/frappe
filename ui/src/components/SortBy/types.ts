/** A single ordering rule: a field plus a direction. A list's ordering is an
 *  ordered list of Sorts. See CONTEXT.md ("Sort"). */
export interface Sort {
  fieldname: string;
  direction: "asc" | "desc";
}

/** A sortable field offered by the control, derived from doctype Meta. Shape
 *  mirrors CRM's `sort_options` rows (`value === fieldname`) so existing hosts
 *  drop in unchanged. See CONTEXT.md ("Field Options"). */
export interface SortOption {
  label: string;
  value: string;
  fieldname: string;
}

/** Props for `<SortBy>`. The ordering rules are a separate `v-model` (`Sort[]`). */
export interface SortByProps {
  /** Doctype whose Meta drives the sortable field options. */
  doctype: string;
  /** Hide the "Sort" label/prefix. */
  hideLabel?: boolean;
}
