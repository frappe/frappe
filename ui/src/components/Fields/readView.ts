import type { FieldNode } from "../FormLayout/types";

/**
 * Fieldtypes whose control draws its own read view, so a read-only one keeps it:
 * a title link, a checkbox, stars, rich text, a file or image, a grid, a map, code,
 * or no value at all.
 */
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

/**
 * Whether a field draws the read look (`ReadOnlyField`) instead of its control: the
 * user cannot edit it (the `Read Only` type, `read_only`, or above their permlevel,
 * all of which arrive as `readOnly`), and no `ui.component` replaces the control.
 */
export function drawsReadValue(field: FieldNode): boolean {
  return !!field.readOnly && !field.ui?.component && !OWN_READ_VIEW.has(field.fieldtype);
}
