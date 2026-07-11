import type { RawMetaField } from "../FormLayout/types";
import type { Column, SyntheticColumn, WireColumn } from "./types";

/** The leading character reserved for a synthetic column's `key` (ADR-0033), so it
 *  can never collide with a docfield. A `_`-prefixed column in a persisted layout is
 *  only valid while a live declaration still claims it — see
 *  {@link dropOrphanedSyntheticColumns}. */
export const SYNTHETIC_KEY_PREFIX = "_";

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
 * left-aligned `Data` column. A Column whose `fieldname` matches a host-declared
 * synthetic column (ADR-0033) takes its render metadata from the declaration instead
 * of Meta. The inverse of {@link parseColumns}.
 */
export function serializeColumns(
  columns: Column[],
  fields: RawMetaField[],
  synthetic: SyntheticColumn[] = []
): WireColumn[] {
  const byName = new Map(fields.map((f) => [f.fieldname, f]));
  const bySynthetic = new Map(synthetic.map((s) => [s.key, s]));
  const autoWidth = (i: number) => (i === 0 ? AUTO_LEADING_FR : AUTO_FR);
  return columns.map((c, i) => {
    const declaration = bySynthetic.get(c.fieldname);
    if (declaration) return syntheticWireColumn(c, declaration, autoWidth(i));
    const field = byName.get(c.fieldname);
    const type = field?.fieldtype ?? "Data";
    return {
      key: c.fieldname,
      label: c.label,
      width: c.width ?? autoWidth(i),
      type,
      options: field?.options,
      align: getColumnAlign(type),
    };
  });
}

/** The wire form of a synthetic column (ADR-0033): its `type`/`align` come from the
 *  host declaration (never Meta), while a user resize (`column.width`) still overrides
 *  the declaration's default width, falling back to the auto `fr` when neither is set. */
function syntheticWireColumn(
  column: Column,
  declaration: SyntheticColumn,
  autoWidth: number
): WireColumn {
  const type = declaration.type ?? "Data";
  return {
    key: column.fieldname,
    label: column.label,
    width: column.width ?? declaration.width ?? autoWidth,
    type,
    options: undefined,
    align: declaration.align ?? getColumnAlign(type),
  };
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

/**
 * Drop **orphaned synthetic columns** from a persisted layout: any `_`-prefixed
 * column (a synthetic `key`, ADR-0033) no longer claimed by a live declaration. A
 * customized layout can outlive the declaration that seeded it — the host stops
 * declaring the Record indicator, yet `_indicator` still sits in the stored
 * `Column[]`. Left in, it names no docfield, so `serializeColumns` mistakes it for a
 * `Data` field and `fetchFields` requests it, erroring `get_list`. This scrubs it on
 * read, keeping the rest of the user's customization; a docfield column (no `_`) is
 * always kept. Returns the same reference when nothing is orphaned (byte-identical),
 * so a layout with no synthetic residue is untouched.
 */
export function dropOrphanedSyntheticColumns(
  columns: Column[],
  synthetic: SyntheticColumn[]
): Column[] {
  const live = new Set(synthetic.map((s) => s.key));
  const isOrphan = (c: Column) =>
    c.fieldname.startsWith(SYNTHETIC_KEY_PREFIX) && !live.has(c.fieldname);
  return columns.some(isOrphan) ? columns.filter((c) => !isOrphan(c)) : columns;
}

/**
 * The field set `get_list` fetches for a set of wire columns: `name` plus each
 * column's key, minus the host-declared synthetic columns (ADR-0033). A synthetic
 * key (`_indicator`) names no docfield, so requesting it would error the fetch —
 * the real fields its cell reads are the host's concern, fetched separately. Deduped.
 * With no synthetic declarations it is `name` + every key (byte-identical default).
 * The library-side companion to a host's own fetch-field builder.
 */
export function fetchFields(
  wire: WireColumn[],
  synthetic: SyntheticColumn[] = []
): string[] {
  const syntheticKeys = new Set(synthetic.map((s) => s.key));
  const keys = wire.map((c) => c.key).filter((key) => !syntheticKeys.has(key));
  return Array.from(new Set(["name", ...keys]));
}
