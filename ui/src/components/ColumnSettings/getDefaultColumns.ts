import type { RawMetaField } from "../FormLayout/types";
import type { Column } from "./types";

/** The `name` standard field, shown first in every default column set — the list
 *  always surfaces the record's identifier as its leading column (the column
 *  analog of the Name quick filter in `getQuickFilterFields`). */
const nameColumn = (): Column => ({ fieldname: "name", label: "Name" });

/**
 * Derive a doctype's default shown Columns from its Meta — the column analog of
 * `getQuickFilterFields`. The fields a doctype flags `in_list_view` are its
 * default columns (Frappe's own list-view convention), mapped to the `Column`
 * shape with the `name` column prepended. `width` is left unset so it falls back
 * to the default at serialize time. Used by `useListView` as the seed the
 * ColumnSettings control customizes; not a CRM columns endpoint.
 */
export function getDefaultColumns(fields: RawMetaField[]): Column[] {
  return [
    nameColumn(),
    ...fields
      .filter((f) => f.in_list_view)
      .map((f) => ({ fieldname: f.fieldname, label: f.label ?? f.fieldname })),
  ];
}
