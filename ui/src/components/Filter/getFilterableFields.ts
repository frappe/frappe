import type { RawMetaField } from "../FormLayout/types";
import type { FilterField } from "./types";

/** Fieldtypes a doctype can be filtered on. A port of the `allowed_fieldtypes`
 *  whitelist in CRM's `crm.api.doc.get_filterable_fields`. */
const FILTERABLE_FIELDTYPES = new Set([
  "Autocomplete",
  "Check",
  "Data",
  "Float",
  "Int",
  "Currency",
  "Dynamic Link",
  "Link",
  "Long Text",
  "Select",
  "Small Text",
  "Text Editor",
  "Text",
  "Duration",
  "Rating",
  "Date",
  "Datetime",
]);

/** Standard fields every doctype can be filtered on, prepended ahead of the
 *  meta fields. Mirrors the `standard_fields` list in `get_filterable_fields`. */
const STANDARD_FIELDS: ReadonlyArray<
  Pick<RawMetaField, "fieldname" | "fieldtype" | "label" | "options">
> = [
  { fieldname: "name", fieldtype: "Link", label: "Name", options: undefined },
  {
    fieldname: "owner",
    fieldtype: "Link",
    label: "Created By",
    options: "User",
  },
  {
    fieldname: "modified_by",
    fieldtype: "Link",
    label: "Last Updated By",
    options: "User",
  },
  { fieldname: "_user_tags", fieldtype: "Data", label: "Tags" },
  { fieldname: "_liked_by", fieldtype: "Data", label: "Like" },
  { fieldname: "_comments", fieldtype: "Text", label: "Comments" },
  { fieldname: "_assign", fieldtype: "Text", label: "Assigned To" },
  { fieldname: "creation", fieldtype: "Datetime", label: "Created On" },
  { fieldname: "modified", fieldtype: "Datetime", label: "Last Updated On" },
];

const toFilterField = (
  f: Pick<RawMetaField, "fieldname" | "fieldtype" | "label" | "options">
): FilterField => ({
  label: f.label ?? f.fieldname,
  value: f.fieldname,
  fieldname: f.fieldname,
  fieldtype: f.fieldtype,
  options: f.options,
});

/**
 * Derive a doctype's filterable Field Options from its Meta fields, client-side.
 * A pure port of `crm.api.doc.get_filterable_fields`: prepend the standard
 * fields, keep only filterable fieldtypes, and stamp `label`/`value`/`fieldname`
 * onto each. The server's per-controller `restricted_fields` hook has no
 * client-side equivalent and is not applied here.
 *
 * `doctype` is the doctype being filtered; it backs the `name` standard field's
 * Link target (`options`), so an `equals`/`in` filter on Name searches the
 * doctype's own records — matching the server's `"options": doctype`.
 */
export function getFilterableFields(
  fields: RawMetaField[],
  doctype: string
): FilterField[] {
  const standardFields = STANDARD_FIELDS.map((f) =>
    f.fieldname === "name" ? { ...f, options: doctype } : f
  );
  return [...standardFields, ...fields]
    .filter((f) => FILTERABLE_FIELDTYPES.has(f.fieldtype))
    .map(toFilterField);
}
