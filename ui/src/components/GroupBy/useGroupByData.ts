import { computed, ref, toValue, watch } from "vue";
import type { ComputedRef, MaybeRefOrGetter, Ref } from "vue";
import { createResource } from "frappe-ui";
import type { WireFilters } from "../Filter/filters";
import { serializeGroupBy, serializeGroupByTotals } from "./groupBy";
import type { GroupBySettings } from "./types";

/**
 * The grouped-data layer — the fetching companion to `GroupBy`, as `useListData` is
 * to the List View controls. The controls stay fetch-free; a host that wants grouped
 * rows out of the box opts in here, and a host with its own data layer runs
 * `serializeGroupBy` itself.
 *
 * It fetches one row per group through `frappe.client.get_list`, plus the group keys
 * alone for the footer's "of N" (there's no count of distinct groups to ask for),
 * capped at `countCap` so a field with many values can't pull the whole list.
 * Any change to the doctype, grouping, filters or page length refetches from the
 * first page; `loadMore` grows the page by one page length. With `showTotals`, a
 * third ungrouped query gives the totals row.
 */
export interface UseGroupByData {
  /** One row per group, as `GroupByTable`'s `rows`. */
  rows: ComputedRef<Record<string, unknown>[]>;
  /** The aggregates over every matching record, as `GroupByTable`'s `totals`;
   *  fetched only while the grouping's `showTotals` is on. */
  totals: ComputedRef<Record<string, unknown> | null>;
  /** Whether the groups are being fetched. */
  loading: ComputedRef<boolean>;
  /** Groups currently loaded — the footer's `rowCount`. */
  rowCount: ComputedRef<number>;
  /** Groups matching the filters — the footer's `totalCount`. */
  totalCount: ComputedRef<number>;
  /** The total hit the cap and is a floor — the footer's `totalCapped`. */
  totalCapped: ComputedRef<boolean>;
  /** False until the total lands — the footer's `hasCounts`. */
  hasCounts: ComputedRef<boolean>;
  /** Whether more groups can be loaded, even past a capped total — the footer's
   *  `hasNextPage`. */
  hasNextPage: ComputedRef<boolean>;
  /** The page length; ListFooter `v-model`s this and a change refetches. */
  pageLength: Ref<number>;
  /** Show one more page of groups. */
  loadMore: () => void;
  /** Refetch from the first page. */
  reload: () => void;
}

/** Defaults a host can override through `UseGroupByDataOptions`. */
export const GROUP_BY_DATA_DEFAULTS = {
  /** Groups per page, the same as the List module's footer starts at. */
  pageLength: 20,
  /** Most group keys fetched to count the groups; past it the total is a floor. */
  countCap: 1000,
};

export interface UseGroupByDataOptions {
  pageLength?: number;
  countCap?: number;
}

export function useGroupByData(
  doctype: MaybeRefOrGetter<string>,
  groupBy: MaybeRefOrGetter<GroupBySettings | null>,
  filters: MaybeRefOrGetter<WireFilters | Record<string, unknown>>,
  options: UseGroupByDataOptions = {}
): UseGroupByData {
  const { pageLength: initialPageLength, countCap } = {
    ...GROUP_BY_DATA_DEFAULTS,
    ...options,
  };
  const pageLength = ref(initialPageLength);
  const limit = ref(initialPageLength);

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
        limit_page_length: countCap,
      };
    },
  });

  const totals = createResource({
    url: "frappe.client.get_list",
    makeParams: () => ({
      doctype: toValue(doctype),
      filters: toValue(filters),
      ...serializeGroupByTotals(toValue(groupBy) as GroupBySettings),
      limit_page_length: 1,
    }),
  });

  // An ungrouped list fetches nothing; the host shows its records instead.
  function reload() {
    const settings = toValue(groupBy);
    if (!settings) return;
    limit.value = pageLength.value;
    groups.fetch();
    groupKeys.fetch();
    if (settings.showTotals && serializeGroupByTotals(settings)) totals.fetch();
  }

  function loadMore() {
    limit.value += pageLength.value;
    groups.fetch();
  }

  // Only what reaches the query refetches: column widths live on the grouping too,
  // and a resize must not reset the loaded pages.
  const query = computed(() => {
    const settings = toValue(groupBy);
    if (!settings) return null;
    return JSON.stringify([serializeGroupBy(settings), settings.showTotals]);
  });

  watch(
    [() => toValue(doctype), query, () => toValue(filters), pageLength],
    reload,
    { immediate: true, deep: true }
  );

  const rows = computed<Record<string, unknown>[]>(() =>
    toValue(groupBy) ? groups.data ?? [] : []
  );

  const totalCount = computed<number>(() => groupKeys.data?.length ?? 0);
  const totalCapped = computed(() => totalCount.value >= countCap);

  return {
    rows,
    totals: computed(() => {
      const settings = toValue(groupBy);
      // Without aggregates there's nothing to total, whatever an earlier fetch left.
      if (!settings?.showTotals || !serializeGroupByTotals(settings))
        return null;
      return (totals.data as Record<string, unknown>[] | null)?.[0] ?? null;
    }),
    loading: computed(() => Boolean(groups.loading)),
    rowCount: computed(() => rows.value.length),
    totalCount,
    totalCapped,
    hasCounts: computed(() => Boolean(groupKeys.data)),
    // Past a capped total, a full page is the only sign more groups exist.
    hasNextPage: computed(() =>
      totalCapped.value
        ? rows.value.length >= limit.value
        : rows.value.length < totalCount.value
    ),
    pageLength,
    loadMore,
    reload,
  };
}
