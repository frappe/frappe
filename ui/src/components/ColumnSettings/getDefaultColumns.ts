import type { RawMetaField } from "../FormLayout/types";
import type { Column } from "./types";

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
