import { computed, ref } from "vue";
import type { Ref, WritableComputedRef } from "vue";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { serializeFilters } from "../Filter/filters";
import type { WireFilters } from "../Filter/filters";
import type { FilterCondition, FilterField } from "../Filter";
import { serializeOrderBy } from "../SortBy/orderBy";
import type { Sort } from "../SortBy";
import { getQuickFilterFields } from "../QuickFilter/getQuickFilterFields";
import { getFilterableFields } from "../Filter/getFilterableFields";

export interface UseListView {
  /** The single source of truth for filter conditions — both the Filter and the
   *  QuickFilter controls `v-model` this same array, so they stay in sync with no
   *  cross-control events. */
  filters: Ref<FilterCondition[]>;
  /** The list's sort order; the SortBy control binds this. */
  sorts: Ref<Sort[]>;
  /** The fields surfaced as QuickFilter inputs. Defaults to the doctype's
   *  `in_standard_filter` fields (from Meta) until customized; a host may bind
   *  this (alongside QuickFilter's `v-model:fields`) to persist the choice. */
  quickFilterFields: WritableComputedRef<FilterField[]>;
  /** Whether the quick-filter strip is in customize (edit) mode. Owned here so a
   *  customize trigger can live anywhere — not just beside QuickFilter — and still
   *  drive its edit state. QuickFilter `v-model:customizing`s this. */
  customizing: Ref<boolean>;
  /** Whether the doctype offers any filterable field to surface — a trigger reads
   *  this to hide itself when there is nothing to customize. */
  canCustomize: Ref<boolean>;
  /** The Frappe wire filter list a host fetches with (`serializeFilters(filters)`). */
  wireFilters: Ref<WireFilters>;
  /** The Frappe `order_by` string a host fetches with (`serializeOrderBy(sorts)`). */
  orderBy: Ref<string>;
}

/**
 * The composite List View's state owner — the shared composable ADR-0001
 * deferred until two controls needed to share state (Filter + QuickFilter are
 * that moment, ADR-0005). It owns the `Filter[]` SoT plus `sorts` and the
 * surfaced quick-filter fields, and exposes the `wireFilters` / `orderBy`
 * computeds a host fetches with.
 *
 * `doctype` is taken by value, not a reactive ref: the Shell remounts the
 * controls via `:key="doctype"` and `useDoctypeMeta` is cached per doctype
 * string, so reconstructing `useListView` on a doctype switch is cheap and
 * needs no internal reset watch.
 */
export function useListView(doctype: string): UseListView {
  const { meta } = useDoctypeMeta(doctype);

  const filters = ref<FilterCondition[]>([]);
  const sorts = ref<Sort[]>([]);

  // `null` ⇒ "use the Meta-derived default"; a value ⇒ the host/user customized
  // it. A writable computed so the default tracks Meta as it loads, yet a
  // customization (via `v-model:fields`) sticks — no seed watch needed.
  const customQuickFilterFields = ref<FilterField[] | null>(null);
  const quickFilterFields = computed<FilterField[]>({
    get: () =>
      customQuickFilterFields.value ??
      getQuickFilterFields(meta.value?.fields ?? [], doctype),
    set: (value) => {
      customQuickFilterFields.value = value;
    },
  });

  const customizing = ref(false);
  const canCustomize = computed(
    () => getFilterableFields(meta.value?.fields ?? [], doctype).length > 0
  );

  const wireFilters = computed(() => serializeFilters(filters.value));
  const orderBy = computed(() => serializeOrderBy(sorts.value));

  return {
    filters,
    sorts,
    quickFilterFields,
    customizing,
    canCustomize,
    wireFilters,
    orderBy,
  };
}
