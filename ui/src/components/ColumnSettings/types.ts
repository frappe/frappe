/** One shown column in the list: a `fieldname`, a user-overridable `label`, and
 *  an optional fixed CSS `width` (`"11rem"`, `"120px"`). The Column Settings
 *  control's state is an ordered list of Columns — presence means shown, array
 *  order is display order, and `width` is the slice a column resize co-writes. A
 *  column with no `width` is *auto*: it flexes to fill the available space
 *  (`serializeColumns` emits a numeric `fr`); only a resized column carries a
 *  fixed `width`, and dropping it (double-click the resizer) returns it to auto.
 *  A column's `align`/`type`/`options` are not stored here; they are derived from
 *  Meta at render/serialize time. See CONTEXT.md ("Column"). */
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
 *  onto this; `parseColumns` drops them back to a {@link Column}. `width` is a
 *  fixed CSS string (`"150px"`) or a numeric `fr` for an auto/flexing column —
 *  frappe-ui's `getGridTemplateColumns` renders a number as `Nfr`. */
export interface WireColumn {
  label: string;
  key: string;
  width: string | number;
  align: "left" | "right";
  type: string;
  options?: string;
}
