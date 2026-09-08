import type { RawMetaField } from "../FormLayout/types";
import type { Column, SyntheticColumn } from "./types";

/** The `name` standard field — the default leading column when the doctype has
 *  no `title_field`. The list always surfaces the record's identifier first (the
 *  column analog of the Name quick filter in `getQuickFilterFields`). */
const nameColumn = (): Column => ({ fieldname: "name", label: "Name" });

/** The leading column for a default set: the doctype's `title_field` when set
 *  (Frappe surfaces the human-readable title in place of the opaque `name`),
 *  otherwise the `name` column. Falls back to `name` if `title_field` names a
 *  field that isn't in Meta. */
function leadingColumn(fields: RawMetaField[], titleField?: string): Column {
  if (!titleField) return nameColumn();
  const field = fields.find((f) => f.fieldname === titleField);
  if (!field) return nameColumn();
  return { fieldname: field.fieldname, label: field.label ?? field.fieldname };
}

/**
 * Derive a doctype's default shown Columns from its Meta — the column analog of
 * `getQuickFilterFields`. The fields a doctype flags `in_list_view` are its
 * default columns (Frappe's own list-view convention), mapped to the `Column`
 * shape with the leading column prepended. The leading column is the doctype's
 * `title_field` when set, else `name`; the title field is then dropped from the
 * `in_list_view` tail so it isn't listed twice. `width` is left unset so it
 * falls back to the default at serialize time. Used by `useListView` as the seed
 * the ColumnSettings control customizes; not a CRM columns endpoint.
 */
export function getDefaultColumns(
  fields: RawMetaField[],
  titleField?: string
): Column[] {
  const leading = leadingColumn(fields, titleField);
  return [
    leading,
    ...fields
      .filter((f) => f.in_list_view && f.fieldname !== leading.fieldname)
      .map((f) => ({ fieldname: f.fieldname, label: f.label ?? f.fieldname })),
  ];
}

/** Convert a synthetic declaration to its persisted {@link Column} form: the `key`
 *  rides the `fieldname` slot, the declaration's default `width` seeds the column
 *  (dropped when unset so it flexes). Render metadata (`type`/`align`) is never
 *  stored — `serializeColumns` re-derives it from the declaration (ADR-0033). */
function toColumn(declaration: SyntheticColumn): Column {
  const column: Column = {
    fieldname: declaration.key,
    label: declaration.label,
  };
  if (declaration.width) column.width = declaration.width;
  return column;
}

/**
 * Fold host-declared synthetic columns (ADR-0033) into a Meta-derived default seed:
 * each declaration is inserted at its `place` anchor (`'start'` | `'after-title'`
 * [right after the leading title/name column] | `'end'`, default `'end'`), and any
 * docfield it `subsumes` is dropped from the seed (default-only, so it stays
 * re-addable). Columns sharing an anchor keep their declaration order. Seeds the
 * default `shown` *only* — once the user customizes order, the persisted layout wins.
 * With no declarations it returns the seed untouched (same reference), so a consumer
 * that declares none is byte-identical.
 */
export function foldSyntheticColumns(
  defaults: Column[],
  synthetic: SyntheticColumn[]
): Column[] {
  if (!synthetic.length) return defaults;
  const subsumed = new Set(
    synthetic.map((s) => s.subsumes).filter((f): f is string => !!f)
  );
  const kept = defaults.filter((c) => !subsumed.has(c.fieldname));
  // Build each anchor group in one pass so declarations sharing an anchor keep their
  // order — inserting one at a time at a fixed index would reverse them.
  const at = (place: SyntheticColumn["place"]) =>
    synthetic.filter((s) => (s.place ?? "end") === place).map(toColumn);
  const [leading, ...rest] = kept;
  const afterLeading =
    leading === undefined
      ? at("after-title")
      : [leading, ...at("after-title"), ...rest];
  return [...at("start"), ...afterLeading, ...at("end")];
}
