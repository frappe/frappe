import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { getDocumentPart } from "../../api";
import type { Activity, CustomActivity, VisibleTypes } from "./types";
import { compareActivities, dropDuplicateKeys } from "./grouping";
import {
  createLiveUpdates,
  type LiveFeed,
  type Subscribe,
  type Unsubscribe,
} from "./liveUpdates";
import { docKey, trackPendingRows, withPendingRows } from "./pendingRows";

interface ActivityPage {
  /** oldest first */
  activities: Activity[];
  /** cursor for the older page; null once the list has ended */
  next: string | null;
}

const stores = new Map<string, TimelineStore>();

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
  // Rows already held may have missed the socket; a read started now has not.
  store.prefetched.value = !store.fetched.value;
  return store.fetched.value ? Promise.resolve() : store.load();
}

/** The first paint is over: a mount after it catches up, as any late mount does. */
export function endActivityPrefetch(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
) {
  const store = stores.get(storeKey(doctype, docname, visibleTypes));
  if (store) store.prefetched.value = false;
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
  const cacheKey = storeKey(doctype, docname, visibleTypes);
  let store = stores.get(cacheKey);
  if (!store) {
    store = new TimelineStore(doctype, docname, visibleTypes);
    stores.set(cacheKey, store);
    void store.load();
  }
  return store;
}

// filters are part of the cache identity
function storeKey(doctype: string, docname: string, visibleTypes?: VisibleTypes) {
  const types = visibleTypes ? JSON.stringify(visibleTypes) : "*";
  return `${docKey(doctype, docname)}:${types}`;
}

// One store per cache key: reopening a doc is instant, loaded pages survive remounts.
class TimelineStore implements LiveFeed {
  readonly doc: string;
  readonly data = ref<Activity[]>([]);
  readonly loading = ref(false);
  readonly error = ref<unknown>(null);
  /** whether the newest page has ever landed */
  readonly fetched = ref(false);
  /** the newest page was read for a mount still to come, so that mount needs no catch-up */
  readonly prefetched = ref(false);
  readonly next = ref<string | null>(null);
  readonly fetchingOlder = ref(false);
  /** one refetch however many callers ask; resolves when it lands */
  readonly refresh: () => Promise<void>;
  readonly subscribe: Subscribe;
  private newestRead: Promise<void> | undefined;
  private olderRead: Promise<void> | undefined;

  constructor(
    private readonly doctype: string,
    private readonly docname: string,
    private readonly visibleTypes?: VisibleTypes
  ) {
    this.doc = docKey(doctype, docname);
    trackPendingRows(this.doc, this.data);
    this.refresh = debouncedRefresh(
      () => this.load(),
      () => this.newestRead
    );
    const types = typeNames(visibleTypes);
    this.subscribe = createLiveUpdates(doctype, docname, this, types, this.refresh);
  }

  load(): Promise<void> {
    this.newestRead ??= this.readNewest().finally(() => {
      this.newestRead = undefined;
    });
    return this.newestRead;
  }

  loadOlder(): Promise<void> {
    if (this.olderRead) return this.olderRead;
    if (this.next.value === null) return Promise.resolve();
    this.olderRead = this.readOlder(this.next.value).finally(() => {
      this.olderRead = undefined;
    });
    return this.olderRead;
  }

  private async readNewest() {
    this.loading.value = true;
    try {
      this.takeNewest(await this.readPage());
      this.error.value = null;
      this.fetched.value = true;
    } catch (failure) {
      this.error.value = failure;
    } finally {
      this.loading.value = false;
    }
  }

  private takeNewest(page: ActivityPage) {
    const held = { activities: this.data.value, next: this.next.value };
    const feed = this.fetched.value ? mergeNewestPage(held, page) : page;
    this.data.value = feed.activities;
    this.next.value = feed.next;
  }

  private async readOlder(before: string) {
    this.fetchingOlder.value = true;
    try {
      const page = await this.readPage(before);
      const held = this.data.value;
      this.data.value = prependOlder(held, page.activities);
      // a page that adds nothing and hands back its own cursor would repeat forever
      const stuck = this.data.value.length === held.length && page.next === before;
      this.next.value = stuck ? null : page.next;
    } catch (failure) {
      this.error.value = failure;
    } finally {
      this.fetchingOlder.value = false;
    }
  }

  // filtered server-side so the cursor walks only the rows this view shows
  private async readPage(before?: string): Promise<ActivityPage> {
    const params = { types: this.visibleTypes, before };
    const response = await getDocumentPart<ActivityPage>(
      this.doctype,
      this.docname,
      "activity",
      params
    );
    return response.data;
  }
}

/** Held rows older than the page stay, with their cursor, when the page reaches them; else the page alone. */
function mergeNewestPage(held: ActivityPage, page: ActivityPage): ActivityPage {
  const oldest = page.activities[0];
  if (!oldest || page.next === null) return page;
  // no held row at or after the page's oldest: rows between the two were never read
  if (!held.activities.some((a) => compareActivities(a, oldest) >= 0))
    return page;
  const older = held.activities.filter((a) => compareActivities(a, oldest) < 0);
  return { activities: [...older, ...page.activities], next: held.next };
}

function prependOlder(current: Activity[], older: Activity[]): Activity[] {
  const known = new Set(current.map((a) => a.key));
  return [...older.filter((a) => !known.has(a.key)), ...current];
}

// one save can fire several doc_updates: wait a moment, then fetch once
const REFRESH_DEBOUNCE_MS = 300;

// Every trigger in the window joins the same fetch, so one save costs one request.
function debouncedRefresh(
  load: () => Promise<void>,
  running: () => Promise<void> | undefined
): () => Promise<void> {
  let pendingRefresh: Promise<void> | undefined;
  let changedSinceFetch = false;
  return () => {
    if (pendingRefresh) {
      changedSinceFetch = true;
      return pendingRefresh;
    }
    pendingRefresh = (async () => {
      do {
        await new Promise((done) => setTimeout(done, REFRESH_DEBOUNCE_MS));
        // a fetch already running was sent before the change, so it may miss it
        await running()?.catch(() => {});
        changedSinceFetch = false;
        await load();
        // a change that landed mid-fetch is not in what came back: go again
      } while (changedSinceFetch);
    })()
      .catch(() => {})
      .finally(() => {
        pendingRefresh = undefined;
      });
    return pendingRefresh;
  };
}

// the store is shared, so one socket serves every consumer of it
function subscribeWhileMounted(store: TimelineStore) {
  let unsubscribe: Unsubscribe | undefined;
  onMounted(() => {
    unsubscribe = store.subscribe();
  });
  onUnmounted(() => {
    unsubscribe?.();
    unsubscribe = undefined;
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
