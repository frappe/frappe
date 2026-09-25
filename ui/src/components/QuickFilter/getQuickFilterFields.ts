import type { RawMetaField } from "../FormLayout/types";
import type { FilterField } from "../Filter/types";

const toQuickFilterField = (f: RawMetaField): FilterField => ({
  label: f.label ?? f.fieldname,
  value: f.fieldname,
  fieldname: f.fieldname,
  fieldtype: f.fieldtype,
  options: f.options,
});

/** The `name` standard field, surfaced first in every default set. A self-Link
 *  against the doctype (so an `equals` quick filter searches the doctype's own
 *  records, matching `getFilterableFields`); the quick controls treat it as
 *  free-text `like` by default — see `isNameField` in `quickFilters`. */
const nameQuickFilterField = (doctype: string): FilterField => ({
  label: "Name",
  value: "name",
  fieldname: "name",
  fieldtype: "Link",
  options: doctype,
});

/**
 * Derive a doctype's default Quick Filter fields from its Meta — the Quick Filter
 * analog of `getFilterableFields`. A pure port of `crm.api.doc.get_quick_filters`'
 * default branch: the fields flagged `in_standard_filter`, mapped to the same
 * `FilterField` shape the controls consume. The `name` standard field is prepended
 * so every doctype surfaces a Name quick filter first (it backs an `equals` pick
 * against the doctype's own records). No `get_quick_filters` endpoint and no
 * CRM-Lead `converted` stripping.
 */
export function getQuickFilterFields(
  fields: RawMetaField[],
  doctype: string
): FilterField[] {
  return [
    nameQuickFilterField(doctype),
    ...fields.filter((f) => f.in_standard_filter).map(toQuickFilterField),
  ];
}
