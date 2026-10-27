import type { FieldNode } from "../FormLayout/types";

/** Fieldtypes `NumberField` draws. A number has no unset state: Frappe shows `0`. */
export const NUMBER_FIELDTYPES = ["Int", "Long Int", "Float", "Currency", "Percent"];

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

/** Whether a read-only field (`Read Only`, `read_only`, or above the user's permlevel)
 *  draws `ReadOnlyField` instead of its control; a `ui.component` always wins. */
export function drawsReadValue(field: FieldNode): boolean {
  return !!field.readOnly && !field.ui?.component && !OWN_READ_VIEW.has(field.fieldtype);
}
