import { holdsChildRows } from "../Fields/rowIdentity";
import { NO_VALUE } from "../FormLayout/noValueFields";
import type { RawMetaField } from "../FormLayout/types";
import { collabColumns, type ColumnMeta } from "./collabColumns";
import type { ColumnOption, SyntheticColumn } from "./types";

/** A list column can't show a no-value field or a child table. */
export function isColumnFieldtype(fieldtype: string): boolean {
  return !NO_VALUE.has(fieldtype) && !holdsChildRows(fieldtype);
}

/** Standard fields every doctype can show as a column, appended after the meta
 *  fields. */
const STANDARD_FIELDS: ReadonlyArray<{ label: string; fieldname: string }> = [
  { label: "Name", fieldname: "name" },
  { label: "Last Modified", fieldname: "modified" },
  { label: "Created On", fieldname: "creation" },
  { label: "Modified By", fieldname: "modified_by" },
  { label: "Owner", fieldname: "owner" },
];

const toOption = (label: string, fieldname: string): ColumnOption => ({
  label,
  value: fieldname,
  fieldname,
});

/**
 * Derive a doctype's available column Field Options from its Meta fields,
 * client-side: drop the layout/no-data fieldtypes and child tables, keep only
 * fields with both a label and fieldname, then append the standard fields and any
 * host-declared synthetic columns — the union so a hidden synthetic
 * column stays re-addable, since it is not a Meta field. The component filters out
 * already-selected columns; this stays a pure Meta→options map. See CONTEXT.md
 * ("Field Options").
 */
export function getColumnOptions(
  fields: RawMetaField[],
  synthetic: SyntheticColumn[] = [],
  meta: ColumnMeta = {}
): ColumnOption[] {
  const fieldOptions = fields
    .filter(
      (f) => isColumnFieldtype(f.fieldtype) && f.label && f.fieldname
    )
    .map((f) => toOption(f.label as string, f.fieldname));
  const standard = STANDARD_FIELDS.map((f) => toOption(f.label, f.fieldname));
  const collab = collabColumns(meta).map((f) => toOption(f.label, f.fieldname));
  const declared = synthetic.map((s) => toOption(s.label, s.key));
  return [...fieldOptions, ...standard, ...collab, ...declared];
}
