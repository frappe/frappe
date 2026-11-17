// One rule for "may a caller set this field", for a record, a child row and a form dialog.
import { holdsChildRows } from "../Fields/rowIdentity";
import { NO_VALUE } from "./noValueFields";

export interface SettableField {
  fieldtype: string;
  hidden?: unknown;
  readOnly?: unknown;
}

/** Why a caller cannot set the field, to follow its name; undefined when it can. `hidden` and `readOnly` are as resolved now. */
export function whyNotSettable(field: SettableField): string | undefined {
  if (holdsChildRows(field.fieldtype)) return "is a table";
  if (NO_VALUE.has(field.fieldtype)) return "holds no value";
  if (field.hidden) return "is hidden now";
  if (field.readOnly || field.fieldtype === "Read Only") return "is read-only";
}

/** The value as the field holds it: a Check holds 0 or 1, and a caller may send a boolean. */
export function coerceValue(fieldtype: string, value: unknown) {
  return fieldtype === "Check" && typeof value === "boolean" ? Number(value) : value;
}
