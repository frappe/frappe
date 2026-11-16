// What `window.desk.state` reads off a record page: its identity, edits and errors, and on request the fields the form shows.
import type { PageActsHost } from "./pageActs";
import { RecordForm } from "./recordForm";

const VALUE_CHARS = 200;

export function recordFacts({ page, form: rest }: Pick<PageActsHost, "page" | "form">, withFields: boolean) {
  const form = new RecordForm({ page, ...rest });
  const errors = form.errors();
  return {
    doctype: page.doctype,
    ...(!page.isNew && { name: page.docname }),
    docstatus: page.doc.docstatus ?? 0,
    unsaved: page.isNew || page.isDirty,
    ...(Object.keys(errors).length && { errors }),
    ...(withFields && { fields: form.shown().map((field) => fieldFact(field, page.doc)) }),
  };
}

function fieldFact(field: Record<string, any>, doc: Record<string, any>) {
  return {
    label: field.label || field.fieldname,
    fieldname: field.fieldname,
    type: field.fieldtype,
    value: valueFact(doc[field.fieldname]),
    required: !!field.reqd,
    read_only: !!field.readOnly,
  };
}

function valueFact(value: unknown) {
  if (Array.isArray(value)) return `${value.length} rows`;
  return typeof value === "string" && value.length > VALUE_CHARS ? `${value.slice(0, VALUE_CHARS)}…` : value ?? null;
}
