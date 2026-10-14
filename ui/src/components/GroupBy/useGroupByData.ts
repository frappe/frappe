import { computed, ref, toValue, watch } from "vue";
import type { ComputedRef, MaybeRefOrGetter, Ref } from "vue";
import { createResource } from "frappe-ui";
import type { WireFilters } from "../Filter/filters";
import { serializeGroupBy } from "./groupBy";
import type { GroupBySettings } from "./types";

/**
 * The grouped-data layer — the fetching companion to `GroupBy`, as `useListData` is
 * to the List View controls. The controls stay fetch-free; a host that wants grouped
 * rows out of the box opts in here, and a host with its own data layer runs
 * `serializeGroupBy` itself.
 *
 * It fetches one row per group through `frappe.client.get_list`, plus the group keys
 * alone for the footer's "of N" (there's no count of distinct groups to ask for).
 * Any change to the doctype, grouping, filters or page length refetches from the
 * first page; `loadMore` grows the page by one page length.
 */
export interface UseGroupByData {
  /** One row per group, as `GroupByTable`'s `rows`. */
  rows: ComputedRef<Record<string, unknown>[]>;
  /** Whether the groups are being fetched. */
  loading: ComputedRef<boolean>;
  /** Groups currently loaded — the footer's `rowCount`. */
  rowCount: ComputedRef<number>;
  /** Groups matching the filters — the footer's `totalCount`. */
  totalCount: ComputedRef<number>;
  /** False until the total lands — the footer's `hasCounts`. */
  hasCounts: ComputedRef<boolean>;
  /** The page length; ListFooter `v-model`s this and a change refetches. */
  pageLength: Ref<number>;
  /** Show one more page of groups. */
  loadMore: () => void;
  /** Refetch from the first page. */
  reload: () => void;
}

export function useGroupByData(
  doctype: MaybeRefOrGetter<string>,
  groupBy: MaybeRefOrGetter<GroupBySettings | null>,
  filters: MaybeRefOrGetter<WireFilters | Record<string, unknown>>
): UseGroupByData {
  const pageLength = ref(20);
  const limit = ref(20);

  const groups = createResource({
    url: "frappe.client.get_list",
    makeParams: () => ({
      doctype: toValue(doctype),
      filters: toValue(filters),
      ...serializeGroupBy(toValue(groupBy) as GroupBySettings),
      limit_page_length: limit.value,
    }),
  });

  const groupKeys = createResource({
    url: "frappe.client.get_list",
    makeParams: () => {
      const fields = (toValue(groupBy) as GroupBySettings).fields;
      return {
        doctype: toValue(doctype),
        filters: toValue(filters),
        fields,
        group_by: fields.join(", "),
        limit_page_length: 0,
      };
    },
  });

  // An ungrouped list fetches nothing; the host shows its records instead.
  function reload() {
    if (!toValue(groupBy)) return;
    limit.value = pageLength.value;
    groups.fetch();
    groupKeys.fetch();
  }

  function loadMore() {
    limit.value += pageLength.value;
    groups.fetch();
  }

  watch(
    [
      () => toValue(doctype),
      () => toValue(groupBy),
      () => toValue(filters),
      pageLength,
    ],
    reload,
    { immediate: true, deep: true }
  );

  const rows = computed<Record<string, unknown>[]>(() =>
    toValue(groupBy) ? groups.data ?? [] : []
  );

  return {
    rows,
    loading: computed(() => Boolean(groups.loading)),
    rowCount: computed(() => rows.value.length),
    totalCount: computed(() => groupKeys.data?.length ?? 0),
    hasCounts: computed(() => Boolean(groupKeys.data)),
    pageLength,
    loadMore,
    reload,
  };
}
