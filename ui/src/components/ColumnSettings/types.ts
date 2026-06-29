/** One shown column in the list: a `fieldname`, a user-overridable `label`, and
 *  an optional CSS `width` (`"11rem"`, `"120px"`). The Column Settings control's
 *  state is an ordered list of Columns — presence means shown, array order is
 *  display order, and `width` is the slice a column resize co-writes. A column's
 *  `align`/`type`/`options` are not stored here; they are derived from Meta at
 *  render/serialize time. See CONTEXT.md ("Column"). */
export interface Column {
  fieldname: string;
  label: string;
  width?: string;
}

/** A column the control offers to add, derived from doctype Meta. Shape mirrors
 *  the other controls' Field Options (`value === fieldname`) so it drops straight
 *  into an Autocomplete. See CONTEXT.md ("Field Options"). */
export interface ColumnOption {
  label: string;
  value: string;
  fieldname: string;
}

/** The frappe-ui `ListView` render shape for one column (CRM's `key` ≙
 *  `fieldname`). `serializeColumns` derives `align`/`type`/`options` from Meta
 *  onto this; `parseColumns` drops them back to a {@link Column}. */
export interface WireColumn {
  label: string;
  key: string;
  width: string;
  align: "left" | "right";
  type: string;
  options?: string;
}
