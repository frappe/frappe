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
