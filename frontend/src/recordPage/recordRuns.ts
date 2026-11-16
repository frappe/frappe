// The `record.set_values` run and what the child-row runs share with it; loaded on the first run.
import { ActInvalid } from "@/acts/dispatcher";
import { NO_VALUE } from "@framework/ui/FormLayout/noValueFields";
import type { FormField, ValueForm } from "./recordActs";

type Row = Record<string, any>;
type Values = Record<string, unknown>;

const SET_VALUES = "record.set_values";

export async function setValues(form: ValueForm, values: Values) {
  for (const fieldname of Object.keys(values)) refuse(SET_VALUES, cannotSet(fieldname, form.field(fieldname)));
  const before = { ...form.doc() };
  for (const [fieldname, value] of Object.entries(values)) {
    // The doc is read again for each value: a handler may have replaced it.
    form.doc()[fieldname] = coerce(form.field(fieldname)!.fieldtype, value);
    await form.commit(fieldname);
  }
  return { values: changed(before, form.doc()), errors: form.errors() };
}

/** Why the field cannot be set, in words that say what to do; undefined when it can. */
export function cannotSet(fieldname: string, field: FormField | null): string | undefined {
  if (!field) return `${fieldname} is not a field of this form`;
  if (fieldname.includes(".")) return `${fieldname} is a column of a table; use record.add_child_row or record.set_child_values`;
  if (field.fieldtype === "Table" || field.fieldtype === "Table MultiSelect")
    return `${fieldname} is a table; use record.add_child_row and record.set_child_values`;
  if (NO_VALUE.has(field.fieldtype)) return `${fieldname} holds no value`;
  if (field.hidden) return `${fieldname} is hidden now`;
  if (field.read_only || field.fieldtype === "Read Only") return `${fieldname} is read-only`;
}

/** The value as the field holds it: a Check holds 0 or 1, and a caller may send a boolean. */
export function coerce(fieldtype: string, value: unknown) {
  return fieldtype === "Check" && typeof value === "boolean" ? Number(value) : value;
}

/** The scalars that differ after, as the caller would read them back. */
export function changed(before: Row, after: Row): Values {
  return Object.fromEntries(
    Object.entries(after).filter(([key, value]) => !key.startsWith("__") && !Array.isArray(value) && !Object.is(before[key], value)),
  );
}

export function refuse(act: string, reason: string | undefined) {
  if (reason) throw new ActInvalid(act, reason);
}
