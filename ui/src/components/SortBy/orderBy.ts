import type { Sort } from "./types";

/** Parse a Frappe `order_by` string (e.g. `"modified desc, name asc"`) into an
 *  ordered list of Sorts. */
export function parseOrderBy(orderBy: string): Sort[] {
  if (!orderBy.trim()) return [];
  return orderBy.split(",").map((rule) => {
    const [fieldname, direction] = rule.trim().split(/\s+/);
    return { fieldname, direction: direction === "desc" ? "desc" : "asc" };
  });
}

/** Serialize a list of Sorts into the Frappe `order_by` wire string. The inverse
 *  of {@link parseOrderBy}; an empty list serializes to `""`. */
export function serializeOrderBy(sorts: Sort[]): string {
  return sorts.map((s) => `${s.fieldname} ${s.direction}`).join(", ");
}
