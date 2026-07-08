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

/** A **synthetic column**: a list column the *host* declares instead of resolving
 *  from doctype Meta, carrying its own render metadata (ADR-0033). It is a first-class
 *  member of the column state — it lives in `shown`, persists in the View Snapshot, and
 *  appears in ColumnSettings — but the library only *declares* it; the host draws its
 *  cell (via the `#cell` slot's `type` hint). Declaration (static, host-authored) and
 *  state (dynamic, user-owned) stay disjoint: the persisted {@link Column} shape does not
 *  change — a synthetic column rides the `fieldname` slot with its `key` (reserved leading
 *  `_`, e.g. `_indicator`, so it can never collide with a docfield). Passed to
 *  `useColumns(doctype, { synthetic })` (threaded from `useListView`). */
export interface SyntheticColumn {
  /** The reserved identity (leading `_`), matched against `shown` at serialize time. */
  key: string;
  label: string;
  /** Render hint the host's cell slot reads (`'Status'`); also drives `align` default. */
  type?: string;
  align?: "left" | "right";
  /** Default width; a user resize overrides it via the Column's own `width`. */
  width?: string;
  /** Default position anchor for the fold into the seed (default `'end'`). */
  place?: "start" | "after-title" | "end";
  /** A docfield this column replaces — dropped from the *default seed only*, not a
   *  render block, so it stays re-addable from the picker (renders plain text). */
  subsumes?: string;
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
