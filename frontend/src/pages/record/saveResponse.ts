// What the page makes of a failed save: the conflict it throws, the message it shows,
// and the fields the reader would lose.
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";
import type { Confirm } from "./discardChanges";

/** The name a save rejected for a conflict throws under; the dialog has already told the reader. */
export const SAVE_CONFLICT = "SaveConflict";

/** The name a save rejected for compile errors throws under; the dialog has listed them. */
export const SAVE_CODE_ERRORS = "SaveCodeErrors";

/** Whether a dialog has already told the reader why the save failed. */
export function shownInDialog(error: unknown): boolean {
  const name = (error as Error | null)?.name;
  return name === SAVE_CONFLICT || name === SAVE_CODE_ERRORS;
}

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

/** Asks whether to reload over a save someone else made first; true for Reload. */
export async function confirmConflict(
  confirm: Confirm,
  editor: string,
  changed: string[],
): Promise<boolean> {
  const mine = changed.length ? __("your changes to {0}", [changed.join(", ")]) : __("your changes");
  const reload = await confirm({
    title: __("Saved by someone else"),
    message: __(
      "{0} saved this record after you opened it, so {1} cannot be saved over theirs. Reload to see their version, or keep editing to copy your values out first.",
      [editor, mine],
    ),
    confirmLabel: __("Reload and lose my changes"),
    cancelLabel: __("Keep editing"),
  });
  return !!reload;
}

export function conflictError(): Error {
  const error = new Error("Saved elsewhere; reload to save your changes.");
  error.name = SAVE_CONFLICT;
  return error;
}

export function codeErrorsError(message: string): Error {
  const error = new Error(message);
  error.name = SAVE_CODE_ERRORS;
  return error;
}
