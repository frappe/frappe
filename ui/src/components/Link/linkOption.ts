import type { LinkOption } from "./types";

/** A `search_link` row as a picker option. When a doctype shows titles in links,
 *  Frappe leads the description with the record's name, which the label already
 *  stands for, so the name is left out. */
export function toLinkOption(row: {
  value: string;
  label?: string;
  description?: string;
}): LinkOption {
  const description = row.description
    ?.split(", ")
    .filter((part) => part !== row.value)
    .join(", ");
  return {
    label: row.label || row.value,
    value: row.value,
    description: description || undefined,
  };
}
