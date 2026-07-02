/** A precise, fieldtype-aware condition on a doctype field, set through the
 *  Filter control. A list's narrowing is a list of Filters. See CONTEXT.md
 *  ("Filter"). */
export interface Filter {
  fieldname: string;
  operator: FilterOperator;
  value: FilterValue;
  /** The field's Meta the control renders the row from; optional for the pure
   *  wire helpers, populated by the control. */
  field?: FilterField;
}

/** The operators a Filter condition can use, in CRM's vocabulary (the UI form,
 *  not the Frappe wire form — `serializeFilters` maps these to wire operators). */
export type FilterOperator =
  | "equals"
  | "not equals"
  | "like"
  | "not like"
  | "in"
  | "not in"
  | "is"
  | "is not"
  | "<"
  | ">"
  | "<="
  | ">="
  | "between"
  | "timespan";

/** A condition's value: a scalar, a list (`in`/`not in`), or a `[from, to]`
 *  pair (`between`). */
export type FilterValue = string | boolean | string[];

/** A filterable field offered by the control, derived from doctype Meta. Shape
 *  mirrors CRM's `get_filterable_fields` rows (`value === fieldname`) so existing
 *  hosts drop in unchanged. See CONTEXT.md ("Field Options"). */
export interface FilterField {
  label: string;
  value: string;
  fieldname: string;
  fieldtype: string;
  options?: string;
}
