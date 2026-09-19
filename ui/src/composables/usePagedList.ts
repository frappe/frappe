// One doctype's rows a page at a time; `reload` starts over, `loadMore` appends the next page.
import { computed, ref, toValue } from "vue";
import type { ComputedRef, MaybeRefOrGetter, Ref } from "vue";
import { listDocuments } from "../api";
import type { ListQuery } from "../api";

export type PageQuery = Omit<ListQuery, "start" | "limit">;

export interface UsePagedListOptions {
  pageLength?: MaybeRefOrGetter<number>;
  /** Asks the first page for the total under the same filters; it lands in `count`. */
  withCount?: boolean;
}

export interface UsePagedList<T> {
  rows: ComputedRef<T[]>;
  /** True while a fetch is in flight. */
  loading: ComputedRef<boolean>;
  error: ComputedRef<unknown>;
  hasNextPage: ComputedRef<boolean>;
  /** The total, `null` before the first answer and when the server gave up counting. */
  count: ComputedRef<number | null>;
  /** The total stopped at the server's cap, so it reads as a floor. */
  countCapped: ComputedRef<boolean>;
  reload: () => Promise<void>;
  loadMore: () => Promise<void>;
}

export function usePagedList<T = Record<string, unknown>>(
  doctype: MaybeRefOrGetter<string>,
  query: MaybeRefOrGetter<PageQuery>,
  { pageLength = 20, withCount = false }: UsePagedListOptions = {}
): UsePagedList<T> {
  // Deeply reactive, so a host may patch a row in place (an optimistic mark-as-read) and see it.
  const rows = ref<T[]>([]) as Ref<T[]>;
  const loading = ref(false);
  const error = ref<unknown>(null);
  const hasNextPage = ref(false);
  const count = ref<number | null>(null);
  const countCapped = ref(false);
  let generation = 0;

  // A page that lands after a later request is dropped, so the rows never mix two queries.
  async function fetchPage(start: number): Promise<void> {
    const mine = ++generation;
    loading.value = true;
    const include = withCount && start === 0 ? ["count"] : undefined;
    try {
      const page = await listDocuments<T>(
        toValue(doctype),
        { ...toValue(query), start, limit: toValue(pageLength) },
        { include }
      );
      if (mine !== generation) return;
      rows.value = start === 0 ? page.data : [...rows.value, ...page.data];
      hasNextPage.value = page.has_next_page;
      if (include) {
        count.value = page.count ?? null;
        countCapped.value = Boolean(page.count_capped);
      }
      error.value = null;
    } catch (failure) {
      if (mine === generation) error.value = failure;
    } finally {
      if (mine === generation) loading.value = false;
    }
  }

  return {
    rows: computed(() => rows.value),
    loading: computed(() => loading.value),
    error: computed(() => error.value),
    hasNextPage: computed(() => hasNextPage.value),
    count: computed(() => count.value),
    countCapped: computed(() => countCapped.value),
    reload: () => fetchPage(0),
    loadMore: () =>
      hasNextPage.value && !loading.value ? fetchPage(rows.value.length) : Promise.resolve(),
  };
}
