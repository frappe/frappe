import { computed, ref, watch } from "vue";
import type { ComputedRef, Ref } from "vue";
import { createListResource, createResource } from "frappe-ui";
import { fetchFields } from "../ColumnSettings/columns";
import type { UseListView } from "./useListView";

/**
 * The list-data layer — the half ADR-0001 deferred to the *host*: the shared
 * composables own filter/sort/column STATE and emit wire projections, but never
 * fetch. This turns those projections into live rows.
 *
 * It's the optional fetching companion to `useListView`: any host that wants
 * doctype-agnostic data out of the box can opt in, while hosts with their own
 * data layer keep the controls fetch-free (ADR-0001). It binds
 * `frappe.client.get_list` (rows) + `get_count` (total, which
 * `createListResource` doesn't track) and refetches from the first page whenever
 * a wire projection or the page length changes. `loadMore` is the only thing
 * that grows `start`, so paging append survives a filter edit.
 */
export interface UseListData {
  /** The fetched rows (raw doc dicts), keyed by `name`; ListView's `rows`. */
  rows: ComputedRef<Record<string, unknown>[]>;
  /** Whether a page fetch is in flight (the first page; not `loadMore`). */
  loading: ComputedRef<boolean>;
  /** Rows currently loaded (across pages) — the footer's `rowCount`. */
  rowCount: ComputedRef<number>;
  /** Total rows matching the filters (the footer's `totalCount`). */
  totalCount: ComputedRef<number>;
  /** The page length; ListFooter `v-model`s this and a change refetches. */
  pageLength: Ref<number>;
  /** Grow the loaded set by one page (`start += pageLength`), appending rows. */
  loadMore: () => void;
  /** Refetch the first page (used on mount and on any wire/pageLength change). */
  reload: () => void;
}

export function useListData(doctype: string, view: UseListView): UseListData {
  const pageLength = ref(20);

  // get_list fetches the row key plus every shown column's field, skipping synthetic
  // columns (ADR-0033) — their keys name no docfield, so the host draws those cells.
  const fields = computed(() =>
    fetchFields(view.columns.wire.value, view.columns.synthetic.value)
  );

  const list = createListResource({
    doctype,
    fields: fields.value,
    filters: view.filters.wire.value,
    orderBy: view.sort.orderBy.value || undefined,
    pageLength: pageLength.value,
  });

  // `createListResource` tracks no total, so a sibling count resource — the same
  // doctype-agnostic endpoint CRM's get_data wraps — backs the footer's "of N".
  const count = createResource({
    url: "frappe.client.get_count",
    makeParams: () => ({ doctype, filters: view.filters.wire.value }),
  });

  // Push the latest wire projections into the resource and fetch the first page.
  // `start: 0` discards any loaded pages — a filter/sort/field change starts over.
  function reload() {
    list.update({
      fields: fields.value,
      filters: view.filters.wire.value,
      orderBy: view.sort.orderBy.value || undefined,
      pageLength: pageLength.value,
      start: 0,
    });
    list.list.fetch();
    count.fetch();
  }

  // One watcher drives every fetch but `loadMore`: the wire filters (identity
  // changes as conditions serialize), the order_by string, the field set, and the
  // page length. `immediate` does the mount fetch, so there's no separate `auto`.
  watch(
    [
      () => view.filters.wire.value,
      () => view.sort.orderBy.value,
      () => fields.value,
      pageLength,
    ],
    reload,
    { immediate: true }
  );

  return {
    rows: computed(() => (list.data as Record<string, unknown>[]) ?? []),
    loading: computed(() => Boolean(list.list.loading)),
    rowCount: computed(() => list.data?.length ?? 0),
    totalCount: computed(() => (count.data as number) ?? 0),
    pageLength,
    loadMore: () => list.next(),
    reload,
  };
}
