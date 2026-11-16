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

/** A `search_link` row labelled by its ID, with the title beneath. */
export function toIdOption(row: {
  value: string;
  label?: string;
  description?: string;
}): LinkOption {
  const parts = [row.label, ...(row.description?.split(", ") ?? [])];
  const description = [...new Set(parts)]
    .filter((part) => part && part !== row.value)
    .join(", ");
  return { label: row.value, value: row.value, description: description || undefined };
}
