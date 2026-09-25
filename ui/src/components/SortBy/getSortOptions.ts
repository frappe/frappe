import type { RawMetaField } from "../FormLayout/types";
import type { SortOption } from "./types";

/** Fieldtypes Frappe stores no value for — they can't be sorted on. Ported from
 *  Frappe's Python `frappe.model.no_value_fields` (not exposed client-side). */
const NO_VALUE_FIELDS = new Set([
  "Section Break",
  "Column Break",
  "Tab Break",
  "HTML",
  "Table",
  "Table MultiSelect",
  "Button",
  "Image",
  "Fold",
  "Heading",
]);

/** Standard fields every doctype can be sorted on, appended after the meta
 *  fields (matches `crm.api.doc.sort_options`). */
const STANDARD_FIELDS: ReadonlyArray<{ label: string; fieldname: string }> = [
  { label: "Name", fieldname: "name" },
  { label: "Created On", fieldname: "creation" },
  { label: "Last Modified", fieldname: "modified" },
  { label: "Modified By", fieldname: "modified_by" },
  { label: "Owner", fieldname: "owner" },
];

const toOption = (label: string, fieldname: string): SortOption => ({
  label,
  value: fieldname,
  fieldname,
});

/**
 * Derive a doctype's sortable Field Options from its Meta fields, client-side.
 * A pure port of `crm.api.doc.sort_options`: drop no-value fieldtypes, keep only
 * fields with both a label and fieldname, then append the standard fields.
 */
export function getSortOptions(fields: RawMetaField[]): SortOption[] {
  const fieldOptions = fields
    .filter((f) => !NO_VALUE_FIELDS.has(f.fieldtype) && f.label && f.fieldname)
    .map((f) => toOption(f.label as string, f.fieldname));
  const standard = STANDARD_FIELDS.map((f) => toOption(f.label, f.fieldname));
  return [...fieldOptions, ...standard];
}
