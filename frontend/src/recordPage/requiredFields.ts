// The mandatory check a save and a dialog's submit share: each mandatory field shown after
// `depends_on` and still empty, in form order, a child row's cells included.
import { identify, rowKey } from "@framework/ui/fields";
import type { FieldAddress } from "@framework/ui/fields/types";
import {
  applyTabOverride,
  resolveFieldConditionals,
  resolveLayout,
} from "@framework/ui/FormLayout";
import type { FieldNode, FormLayoutSchema } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";

/** A mandatory field the check found empty, with the label of the field the form draws it in. */
export interface MissingField {
  address: FieldAddress;
  message: string;
  /** The field's own label, or its table's for a row cell. */
  shownIn: string;
}

export function missingRequired(
  layout: FormLayoutSchema,
  doc: Record<string, any>,
): MissingField[] {
  const missing: MissingField[] = [];
  for (const field of shownFields(layout, doc)) {
    const label = labelOf(field);
    if (field.reqd && isEmpty(doc[field.fieldname]))
      missing.push({ address: field.fieldname, message: requiredMessage(label), shownIn: label });
    if (field.fieldtype === "Table" && Array.isArray(doc[field.fieldname]))
      for (const row of doc[field.fieldname])
        for (const cell of missingCells(field, row, doc)) missing.push({ ...cell, shownIn: label });
  }
  return missing;
}

/** The top-level fields the form shows, in order: hidden tabs, sections and fields left out. */
export function shownFields(
  layout: FormLayoutSchema,
  doc: Record<string, any>,
  parent: Record<string, any> = doc,
): FieldNode[] {
  return resolveLayout(layout, doc, parent)
    .filter((tab) => !applyTabOverride(tab).hidden)
    .flatMap((tab) => tab.sections.filter((section) => !section.hidden))
    .flatMap((section) => section.columns.flatMap((column) => column.fields))
    .filter((field) => !field.hidden);
}

/** The refusal a record page's save shows, naming each field it marked or the table it sits in. */
export function requiredRefusal(missing: MissingField[]): string {
  return __("Please fill in {0}", [[...new Set(missing.map((one) => one.shownIn))].join(", ")]);
}

// The row dialog's layout when there is one, so a cell its hidden section holds is not demanded.
function missingCells(table: FieldNode, row: Record<string, any>, doc: Record<string, any>) {
  const layout = table.rowLayout?.(row) ?? table.childLayout;
  const fields = layout
    ? shownFields(layout, row, doc)
    : (table.childFields ?? [])
        .map((field) => resolveFieldConditionals(field, row, doc))
        .filter((field) => !field.hidden);
  return fields
    .filter((field) => field.reqd && isEmpty(row[field.fieldname]))
    .map((field) => ({
      address: { parentfield: table.fieldname, key: rowKey(identify(row))!, fieldname: field.fieldname },
      message: requiredMessage(labelOf(field)),
    }));
}

function requiredMessage(label: string): string {
  return __("{0} is required", [label]);
}

function labelOf(field: FieldNode): string {
  return field.label || field.fieldname;
}

function isEmpty(value: any): boolean {
  if (Array.isArray(value)) return value.length === 0;
  return value == null || value === "";
}
