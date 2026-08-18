import { computed, ref } from "vue";
import type { Ref } from "vue";
import { serializeFilters } from "./filters";
import type { WireFilters } from "./filters";
import type { FilterCondition } from "./types";

export interface UseFilters {
  /** The single source of truth for filter conditions — both the Filter and the
   *  QuickFilter controls `v-model` this same array, so they stay in sync with no
   *  cross-control events (ADR-0005). */
  conditions: Ref<FilterCondition[]>;
  /** The Frappe wire filter list a host fetches with (`serializeFilters`). */
  wire: Ref<WireFilters>;
}

/**
 * Owns the shared `FilterCondition[]` both filter controls bind, plus the wire
 * projection a host fetches with. Needs no Meta — the conditions carry their own
 * field, so this is pure list + serialize.
 */
export function useFilters(): UseFilters {
  const conditions = ref<FilterCondition[]>([]);
  const wire = computed(() => serializeFilters(conditions.value));
  return { conditions, wire };
}
