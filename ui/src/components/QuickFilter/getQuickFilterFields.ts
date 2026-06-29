import type { RawMetaField } from "../FormLayout/types";
import type { FilterField } from "../Filter/types";

const toQuickFilterField = (f: RawMetaField): FilterField => ({
  label: f.label ?? f.fieldname,
  value: f.fieldname,
  fieldname: f.fieldname,
  fieldtype: f.fieldtype,
  options: f.options,
});

/**
 * Derive a doctype's default Quick Filter fields from its Meta — the Quick Filter
 * analog of `getFilterableFields`. A pure port of `crm.api.doc.get_quick_filters`'
 * default branch: the fields flagged `in_standard_filter`, mapped to the same
 * `FilterField` shape the controls consume. No `get_quick_filters` endpoint, no
 * CRM-Lead `converted` stripping, and — matching the server default — no `name`
 * field (it is reachable only through the customize/add picker, which draws from
 * `getFilterableFields`).
 */
export function getQuickFilterFields(fields: RawMetaField[]): FilterField[] {
  return fields.filter((f) => f.in_standard_filter).map(toQuickFilterField);
}
