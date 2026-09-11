// What a failed `frappe.client.save` answers, read into the two things the page acts on:
// a timestamp mismatch, and the message the server meant the reader to see.
import type { RawMetaField } from "@framework/ui/components/FormLayout/types";

/** The name a save rejected for a conflict throws under; the dialog has already told the reader. */
export const SAVE_CONFLICT = "SaveConflict";

export function isTimestampMismatch(body: any): boolean {
  return body?.exc_type === "TimestampMismatchError";
}

/** The server's first `msgprint`, or nothing; `_server_messages` is a JSON list of JSON strings. */
export function serverMessage(body: any): string | undefined {
  try {
    const messages: string[] = JSON.parse(body?._server_messages ?? "[]");
    const first = messages[0] && JSON.parse(messages[0]);
    return typeof first?.message === "string" ? first.message : undefined;
  } catch {
    return undefined;
  }
}

/** The labels of the fields the draft changed, in meta order, then any key the meta does not carry. */
export function changedFields(
  doc: Record<string, any>,
  saved: Record<string, any>,
  fields: RawMetaField[] | undefined,
): string[] {
  const changed = new Set(
    [...Object.keys(doc), ...Object.keys(saved)].filter(
      (key) => !key.startsWith("_") && JSON.stringify(doc[key]) !== JSON.stringify(saved[key]),
    ),
  );
  const labelled: string[] = [];
  for (const field of fields ?? []) {
    if (!changed.delete(field.fieldname)) continue;
    labelled.push(field.label || field.fieldname);
  }
  return [...labelled, ...changed];
}

export function conflictError(): Error {
  const error = new Error("Saved elsewhere; reload to save your changes.");
  error.name = SAVE_CONFLICT;
  return error;
}
