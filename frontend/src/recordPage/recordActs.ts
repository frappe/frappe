// The `record` surface: acts that fill the form in front the way typing does, and never save.
import { ActInvalid, type ActEntry } from "@/acts/dispatcher";

type Row = Record<string, any>;
type Values = Record<string, unknown>;

/** What an act needs to know of a top-level field. */
export interface FormField {
  fieldtype: string;
  hidden?: boolean | 0 | 1;
  read_only?: boolean | 0 | 1;
}

/** The form in front, as `record.set_values` sees it. */
export interface ValueForm {
  doc: () => Row;
  /** The field as it now resolves, or null when the form has none of that name. */
  field: (fieldname: string) => FormField | null;
  /** Commits the value already written to the doc, as typing does, and waits for its handlers. */
  commit: (fieldname: string) => Promise<void>;
  /** The marks on screen: a field's name, or `table.<idx>.<fieldname>` for a cell. */
  errors: () => Record<string, string>;
}

const SET_VALUES = "record.set_values";

export function setValuesEntry(form: ValueForm): ActEntry {
  return {
    item: { name: "set_values", palette: false, run: (_form, value) => setValues(form, value.values) },
    hidden: false,
  };
}

async function setValues(form: ValueForm, values: Values) {
  for (const fieldname of Object.keys(values)) refuse(SET_VALUES, cannotSet(fieldname, form.field(fieldname)));
  const doc = form.doc();
  const before = { ...doc };
  for (const [fieldname, value] of Object.entries(values)) {
    doc[fieldname] = coerce(form.field(fieldname)!.fieldtype, value);
    await form.commit(fieldname);
  }
  return { values: changed(before, doc), errors: form.errors() };
}

/** Why the field cannot be set, in words that say what to do; undefined when it can. */
export function cannotSet(fieldname: string, field: FormField | null): string | undefined {
  if (!field) return `${fieldname} is not a field of this form`;
  if (field.fieldtype === "Table" || field.fieldtype === "Table MultiSelect")
    return `${fieldname} is a table; use record.add_child_row and record.set_child_values`;
  if (field.hidden) return `${fieldname} is hidden now`;
  if (field.read_only) return `${fieldname} is read-only`;
}

/** The value as the field holds it: a Check holds 0 or 1, and a caller may send a boolean. */
export function coerce(fieldtype: string, value: unknown) {
  return fieldtype === "Check" && typeof value === "boolean" ? Number(value) : value;
}

/** The scalars that differ after, as the caller would read them back. */
export function changed(before: Row, after: Row): Values {
  return Object.fromEntries(
    Object.entries(after).filter(
      ([key, value]) => !key.startsWith("__") && !Array.isArray(value) && !Object.is(before[key], value),
    ),
  );
}

export function refuse(act: string, reason: string | undefined) {
  if (reason) throw new ActInvalid(act, reason);
}
