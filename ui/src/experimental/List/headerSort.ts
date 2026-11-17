import type { Sort } from "../../components/SortBy/types";

/** The direction a header shows for its column, or null when the column is not in the sort. */
export function directionFor(
  sort: Sort[],
  fieldname: string
): Sort["direction"] | null {
  return sort.find((entry) => entry.fieldname === fieldname)?.direction ?? null;
}

/** A header click makes its column the whole sort: ascending first, then flipping each click. */
export function nextSort(sort: Sort[], fieldname: string): Sort[] {
  const direction = directionFor(sort, fieldname) === "asc" ? "desc" : "asc";
  return [{ fieldname, direction }];
}
