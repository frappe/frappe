import type { RawMetaField } from "../FormLayout/types";
import type { ColumnOption, SyntheticColumn } from "./types";

/** Fieldtypes that hold no list-renderable value — layout/presentation breaks and
 *  child tables. A column can't be shown for any of these, so they're dropped from
 *  the add-column options. Mirrors CRM ColumnSettings' field filter. */
const NON_COLUMN_FIELDTYPES = new Set([
  "Section Break",
  "Column Break",
  "Tab Break",
  "HTML",
  "Heading",
  "Button",
  "Fold",
  "Table",
  "Table MultiSelect",
]);

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
 * host-declared synthetic columns (ADR-0033) — the union so a hidden synthetic
 * column stays re-addable, since it is not a Meta field. The component filters out
 * already-selected columns; this stays a pure Meta→options map. See CONTEXT.md
 * ("Field Options").
 */
export function getColumnOptions(
  fields: RawMetaField[],
  synthetic: SyntheticColumn[] = []
): ColumnOption[] {
  const fieldOptions = fields
    .filter(
      (f) => !NON_COLUMN_FIELDTYPES.has(f.fieldtype) && f.label && f.fieldname
    )
    .map((f) => toOption(f.label as string, f.fieldname));
  const standard = STANDARD_FIELDS.map((f) => toOption(f.label, f.fieldname));
  const declared = synthetic.map((s) => toOption(s.label, s.key));
  return [...fieldOptions, ...standard, ...declared];
}
