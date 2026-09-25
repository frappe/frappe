import { computed, onMounted, onUnmounted, reactive } from "vue";
import type { Activity, CustomActivity, VisibleTypes } from "./types";
import { compareActivities, dropDuplicateKeys } from "./grouping";
import type { Unsubscribe } from "./liveUpdates";
import { docKey, withPendingRows } from "./pendingRows";
import { StoreCache } from "./storeCache";
import { TimelineStore } from "./timelineStore";

// one store per cache key, kept past unmount so loaded pages survive a remount
const stores = new StoreCache();

export function useActivityTimeline(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
) {
  const store = getTimelineStore(doctype, docname, visibleTypes);
  subscribeWhileMounted(store);

  return {
    activities: shownActivities(store, typeNames(visibleTypes)),
    loading: computed<boolean>(() => store.loading.value),
    error: computed<unknown>(() => store.error.value),
    reload: () => store.refresh(),
    // reactive() so the refs unwrap when read through the `paginate` prop
    paginate: reactive({
      hasNextPage: computed(
        () => store.fetched.value && store.next.value !== null
      ),
      isFetchingNextPage: computed(() => store.fetchingOlder.value),
      fetchNextPage: () => store.loadOlder(),
    }),
  };
}

/** Starts the newest-page read before any component mounts; resolves once that page is in. */
export function prefetchActivityTimeline(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
): Promise<void> {
  const store = getTimelineStore(doctype, docname, visibleTypes);
  // A mounted store's socket kept its rows current; an idle one's may have missed changes, so it re-reads.
  const live = store.fetched.value && store.mounted > 0;
  store.prefetched.value = !live;
  if (live) return Promise.resolve();
  // load() resolves even on failure, so a failed read must not leave the flag claiming a catch-up refresh is unneeded.
  return store.load().then(() => {
    if (store.error.value) store.prefetched.value = false;
  });
}

/** The first paint is over: a mount after it catches up, as any late mount does. */
export function endActivityPrefetch(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
) {
  const store = stores.get(storeKey(doctype, docname, visibleTypes));
  if (!store) return;
  store.prefetched.value = false;
  // A staged first read whose page never ran leaves the store with no rows, so it reads for itself.
  if (!store.fetched.value && store.loading.value) void store.load();
}

/** The rows a store holds, pending ones included, with no component mounted; none if no read began. */
export function activityTimelineRows(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
): Array<Activity | CustomActivity> {
  const store = stores.get(storeKey(doctype, docname, visibleTypes));
  return store ? shownRows(store, typeNames(visibleTypes)) : [];
}

/** True when a store for this read holds its newest page, mounted or kept idle. */
export function hasActivityTimeline(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
): boolean {
  const store = stores.get(storeKey(doctype, docname, visibleTypes));
  return store?.fetched.value === true;
}

/** Reads a store's newest page, its first when none is kept; its rows change only when the returned function runs. Null with a mounted store. */
export function stageActivityTimelineRead(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
): Promise<() => void> | null {
  const store =
    stores.get(storeKey(doctype, docname, visibleTypes)) ??
    addTimelineStore(doctype, docname, visibleTypes);
  if (store.mounted > 0) return null;
  // Marked as a prefetch, so a mount before `endActivityPrefetch` reads nothing more.
  store.prefetched.value = true;
  const first = !store.fetched.value;
  if (first) store.loading.value = true;
  return store.stageNewest().then(
    (take) => () => {
      take();
      if (first) store.loading.value = false;
    },
    (failure) => {
      store.prefetched.value = false;
      if (first) {
        store.loading.value = false;
        store.error.value = failure;
      }
      if (store.mounted > 0) void store.refresh();
      throw failure;
    }
  );
}

/** Re-reads the newest page with no component mounted; with no store yet, it starts the first read. */
export function reloadActivityTimeline(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
): Promise<void> {
  const store = stores.get(storeKey(doctype, docname, visibleTypes));
  return store
    ? store.refresh()
    : prefetchActivityTimeline(doctype, docname, visibleTypes);
}

function getTimelineStore(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
): TimelineStore {
  const store = stores.get(storeKey(doctype, docname, visibleTypes));
  if (store) return store;
  const added = addTimelineStore(doctype, docname, visibleTypes);
  void added.load();
  return added;
}

// cached with no read begun
function addTimelineStore(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
): TimelineStore {
  const types = typeNames(visibleTypes);
  const store = new TimelineStore(doctype, docname, visibleTypes, types);
  stores.add(storeKey(doctype, docname, visibleTypes), store);
  return store;
}

// filters are part of the cache identity
function storeKey(doctype: string, docname: string, visibleTypes?: VisibleTypes) {
  const types = visibleTypes ? JSON.stringify(visibleTypes) : "*";
  return `${docKey(doctype, docname)}:${types}`;
}

// the store is shared, so one socket serves every consumer of it
function subscribeWhileMounted(store: TimelineStore) {
  let unsubscribe: Unsubscribe | undefined;
  onMounted(() => {
    unsubscribe = store.mount();
  });
  onUnmounted(() => {
    unsubscribe?.();
    unsubscribe = undefined;
    stores.evictIdle();
  });
}

// deduped + sorted but ungrouped; the component folds version runs at render time
function shownActivities(store: TimelineStore, types: string[] | undefined) {
  return computed(() => shownRows(store, types));
}

function shownRows(
  store: TimelineStore,
  types: string[] | undefined
): Array<Activity | CustomActivity> {
  const confirmed = dropDuplicateKeys(store.data.value);
  return withPendingRows(store.doc, confirmed, types).sort(compareActivities);
}

function typeNames(visibleTypes?: VisibleTypes): string[] | undefined {
  return visibleTypes?.flatMap((t) =>
    typeof t === "string" ? [t] : Object.keys(t)
  );
}
