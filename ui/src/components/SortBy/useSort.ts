import { computed, ref } from "vue";
import type { Ref } from "vue";
import { serializeOrderBy } from "./orderBy";
import type { Sort } from "./types";

export interface UseSort {
  /** The list's sort order; the SortBy control binds this. */
  by: Ref<Sort[]>;
  /** The Frappe `order_by` string a host fetches with (`serializeOrderBy`). */
  orderBy: Ref<string>;
}

/**
 * Owns the sort order and the `order_by` string a host fetches with. Self-contained
 * (no Meta) — sorts carry their own field and direction.
 */
export function useSort(): UseSort {
  const by = ref<Sort[]>([]);
  const orderBy = computed(() => serializeOrderBy(by.value));
  return { by, orderBy };
}
