import type { RawMetaField } from "../FormLayout/types";
import type { Column, WireColumn } from "./types";

/** Auto-width (fr) a column flexes to when its Column carries no explicit `width`.
 *  frappe-ui's `getGridTemplateColumns` renders a *number* as `fr` (flex, fills
 *  the available track) and a *string* (`"150px"`, `"10rem"`) as a fixed size — so
 *  "auto" is a numeric fr and "fixed" is the px string a drag-resize writes back.
 *  The leading column gets a larger share so the title reads first. */
const AUTO_LEADING_FR = 2;
const AUTO_FR = 1;

/** Fieldtypes whose values read as numbers — right-aligned in the list, matching
 *  CRM's ColumnSettings `addColumn`. Every other fieldtype aligns left. */
const RIGHT_ALIGNED_FIELDTYPES = new Set([
  "Int",
  "Float",
  "Currency",
  "Percent",
  "Duration",
]);

/** A column's text alignment, derived purely from its fieldtype (never stored on
 *  a Column — see CONTEXT.md "Column"). */
export function getColumnAlign(fieldtype: string): "left" | "right" {
  return RIGHT_ALIGNED_FIELDTYPES.has(fieldtype) ? "right" : "left";
}

/**
 * Map an ordered list of Columns to frappe-ui's `ListView` render shape — this
 * doubles as the control's "wire" form. Each Column keeps its stored `label` and
 * `width`, while `type`/`options`/`align` are derived from the matching Meta field
 * (`align` from its fieldtype). A Column with no explicit `width` flexes to fill
 * the available space (a numeric `fr`, larger for the leading column); only a
 * resized column carries a fixed px `width`. A Column with no Meta field — a
 * standard field like `name` that isn't in `meta.fields` — falls back to a
 * left-aligned `Data` column. The inverse of {@link parseColumns}.
 */
export function serializeColumns(
  columns: Column[],
  fields: RawMetaField[]
): WireColumn[] {
  const byName = new Map(fields.map((f) => [f.fieldname, f]));
  return columns.map((c, i) => {
    const field = byName.get(c.fieldname);
    const type = field?.fieldtype ?? "Data";
    return {
      key: c.fieldname,
      label: c.label,
      width: c.width ?? (i === 0 ? AUTO_LEADING_FR : AUTO_FR),
      type,
      options: field?.options,
      align: getColumnAlign(type),
    };
  });
}

/**
 * Recover an ordered list of Columns from frappe-ui's render shape, the inverse
 * of {@link serializeColumns}: keep `fieldname` (from `key`) and `label`, and
 * drop the Meta-derived `type`/`options`/`align` — a Column never stores them
 * (see CONTEXT.md "Column"). Only a fixed string `width` is kept; a numeric `fr`
 * (an auto column) maps back to no stored `width`, the inverse of the auto-fill
 * default `serializeColumns` emits.
 */
export function parseColumns(wire: WireColumn[]): Column[] {
  return wire.map((w) => ({
    fieldname: w.key,
    label: w.label,
    width: typeof w.width === "string" ? w.width : undefined,
  }));
}

/**
 * Write a resized column's new `width` back into the matching Column by
 * `fieldname`, returning a new list (others untouched; a no-op if nothing
 * matches). This is the resize→settings half of the ADR-0006 sync: the `ListView`
 * composite's `columnWidthUpdated` handler calls this on the shared `columns` ref,
 * which ColumnSettings also `v-model`s — so the popover's width follows a drag
 * with no event plumbing.
 */
export function applyColumnWidth(
  columns: Column[],
  fieldname: string,
  width: string
): Column[] {
  return columns.map((c) => (c.fieldname === fieldname ? { ...c, width } : c));
}

/**
 * Drop a column's fixed `width` by `fieldname`, returning it to auto (flex) —
 * the reset half of the resize story. With no stored `width`, `serializeColumns`
 * falls the column back to a flexing `fr`, so the host's double-click-the-resizer
 * gesture lands here. Returns a new list (others untouched; a no-op if nothing
 * matches or the column was already auto).
 */
export function clearColumnWidth(
  columns: Column[],
  fieldname: string
): Column[] {
  return columns.map((c) => {
    if (c.fieldname !== fieldname) return c;
    const { width: _omit, ...rest } = c;
    return rest;
  });
}
