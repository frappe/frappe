import { computed, ref, watch } from "vue";
import type { ComputedRef, Ref } from "vue";
import { countDocuments } from "../../api";
import { fetchFields } from "../ColumnSettings/columns";
import { usePagedList } from "../../composables/usePagedList";
import type { UseListView } from "./useListView";

/**
 * The list-data layer — the half ADR-0001 deferred to the *host*: the shared
 * composables own filter/sort/column STATE and emit wire projections, but never
 * fetch. This turns those projections into live rows.
 *
 * It's the optional fetching companion to `useListView`: any host that wants
 * doctype-agnostic data out of the box can opt in, while hosts with their own
 * data layer keep the controls fetch-free (ADR-0001). It reads the rows and the
 * total in one list request and refetches from the first page whenever a wire
 * projection or the page length changes. `loadMore` is the only thing that grows
 * `start`, so paging append survives a filter edit.
 */
export interface UseListData {
  /** The fetched rows (raw doc dicts), keyed by `name`; ListView's `rows`. */
  rows: ComputedRef<Record<string, unknown>[]>;
  /** Whether a page fetch is in flight (the first page; not `loadMore`). */
  loading: ComputedRef<boolean>;
  /** Rows currently loaded (across pages) — the footer's `rowCount`. */
  rowCount: ComputedRef<number>;
  /** Total rows matching the filters (the footer's `totalCount`); the loaded rows when the count timed out. */
  totalCount: ComputedRef<number>;
  /** The total stopped at the server's cap, so it reads as a floor; `countExact` lifts it. */
  totalCapped: ComputedRef<boolean>;
  /** The server gave up counting; the footer reads "many". */
  totalUnknown: ComputedRef<boolean>;
  /** Asks for the exact total after a capped one; a null or failed answer leaves it as is. */
  countExact: () => Promise<void>;
  /** The page length; ListFooter `v-model`s this and a change refetches. */
  pageLength: Ref<number>;
  /** Grow the loaded set by one page (`start += pageLength`), appending rows. */
  loadMore: () => void;
  /** Refetch the first page (used on mount and on any wire/pageLength change). */
  reload: () => void;
}

export function useListData(doctype: string, view: UseListView): UseListData {
  const pageLength = ref(20);

  // The row key plus every shown column's field, skipping synthetic columns
  // (ADR-0033) — their keys name no docfield, so the host draws those cells.
  const fields = computed(() =>
    fetchFields(view.columns.wire.value, view.columns.synthetic.value)
  );

  const list = usePagedList<Record<string, unknown>>(
    doctype,
    () => ({
      fields: fields.value,
      filters: view.filters.wire.value,
      order_by: view.sort.orderBy.value || undefined,
    }),
    { pageLength, withCount: true }
  );

  // The exact total replaces the included one until the next reload resets it.
  const exact = ref<number | null>(null);
  const count = computed(() => exact.value ?? list.count.value);
  // False until the first page answered without error, so a failure never reads "many".
  const answered = ref(false);
  let generation = 0;

  async function reload() {
    const mine = ++generation;
    exact.value = null;
    answered.value = false;
    await list.reload();
    if (mine === generation) answered.value = list.error.value == null;
  }

  async function countExact() {
    const filters = view.filters.wire.value;
    const { data } = await countDocuments(doctype, { filters }).catch(() => ({ data: null }));
    if (data == null || filters !== view.filters.wire.value) return;
    exact.value = data;
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
    () => void reload(),
    { immediate: true }
  );

  return {
    rows: list.rows,
    loading: computed(() => list.loading.value && list.rows.value.length === 0),
    rowCount: computed(() => list.rows.value.length),
    totalCount: computed(() => count.value ?? list.rows.value.length),
    totalCapped: computed(() => exact.value == null && list.countCapped.value),
    totalUnknown: computed(() => answered.value && count.value == null),
    countExact,
    pageLength,
    loadMore: () => void list.loadMore(),
    reload: () => void reload(),
  };
}
