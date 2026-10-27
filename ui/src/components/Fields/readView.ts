import type { FieldNode } from "../FormLayout/types";

/** Fieldtypes whose control draws its own read view, or that hold no value. */
const OWN_READ_VIEW = new Set([
  "Link",
  "Dynamic Link",
  "Check",
  "Rating",
  "Text Editor",
  "Attach",
  "Attach Image",
  "Image",
  "Signature",
  "Table",
  "Geolocation",
  "Code",
  "JSON",
  "Markdown Editor",
  "HTML Editor",
  "Heading",
  "HTML",
  "Button",
]);

/** Whether a read-only field draws `ReadOnlyField` instead of its control; a `ui.component` wins. */
export function drawsReadValue(field: FieldNode): boolean {
  return !!field.readOnly && !field.ui?.component && !OWN_READ_VIEW.has(field.fieldtype);
}
