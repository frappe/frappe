// Kept apart from `newRowValues` so a caller needing only the set does not pull its number formatting.

/**
 * Frappe's own `no_value_fields` (`frappe/model/__init__.py`) minus the two
 * collection types, which DO hold a value in the document even though they have
 * no column of their own — a nested table's empty is `[]`.
 */
export const NO_VALUE = new Set([
  "Section Break",
  "Column Break",
  "Tab Break",
  "Heading",
  "HTML",
  "Fold",
  "Button",
  "Image",
  "Attachment Gallery",
  "Vue Component",
]);

// One rule for "may a caller set this field", for a record, a child row and a form dialog.
export interface SettableField {
  fieldtype: string;
  hidden?: unknown;
  readOnly?: unknown;
}

type NotSettable = "table" | "no value" | "hidden" | "read-only";

/** Why a caller cannot set the field; undefined when it can. `hidden` and `readOnly` are as resolved now. */
export function whyNotSettable({ fieldtype: type, hidden, readOnly }: SettableField): NotSettable | undefined {
  return type.startsWith("Table")
    ? "table"
    : NO_VALUE.has(type)
      ? "no value"
      : hidden
        ? "hidden"
        : readOnly || type === "Read Only"
          ? "read-only"
          : undefined;
}
