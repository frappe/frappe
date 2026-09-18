// What the page makes of a failed save: the conflict it throws, the message it shows,
// and the fields the reader would lose.
import type { RawMetaField } from "@framework/ui/components/FormLayout/types";

/** The name a save rejected for a conflict throws under; the dialog has already told the reader. */
export const SAVE_CONFLICT = "SaveConflict";

// A msgprint is often HTML; the page renders it as text, so the tags go and a break becomes a space.
export function stripTags(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim();
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
