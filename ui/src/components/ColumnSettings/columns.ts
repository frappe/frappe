import type { RawMetaField } from "../FormLayout/types";
import type { Column, WireColumn } from "./types";

/** The width a column renders at when its Column carries none, matching CRM's
 *  `addColumn` default. */
const DEFAULT_WIDTH = "10rem";

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
 * `width` (defaulting the width), while `type`/`options`/`align` are derived from
 * the matching Meta field (`align` from its fieldtype). A Column with no Meta
 * field — a standard field like `name` that isn't in `meta.fields` — falls back
 * to a left-aligned `Data` column. The inverse of {@link parseColumns}.
 */
export function serializeColumns(
  columns: Column[],
  fields: RawMetaField[]
): WireColumn[] {
  const byName = new Map(fields.map((f) => [f.fieldname, f]));
  return columns.map((c) => {
    const field = byName.get(c.fieldname);
    const type = field?.fieldtype ?? "Data";
    return {
      key: c.fieldname,
      label: c.label,
      width: c.width ?? DEFAULT_WIDTH,
      type,
      options: field?.options,
      align: getColumnAlign(type),
    };
  });
}

/**
 * Recover an ordered list of Columns from frappe-ui's render shape, the inverse
 * of {@link serializeColumns}: keep `fieldname` (from `key`), `label`, and
 * `width`, and drop the Meta-derived `type`/`options`/`align` — a Column never
 * stores them (see CONTEXT.md "Column").
 */
export function parseColumns(wire: WireColumn[]): Column[] {
  return wire.map((w) => ({
    fieldname: w.key,
    label: w.label,
    width: w.width,
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
