import {
  computed,
  onMounted,
  onUnmounted,
  reactive,
  ref,
  watch,
  type Ref,
} from "vue";
import { getDocumentPart } from "../../api";
import type {
  Activity,
  CustomActivity,
  PendingActivity,
  VisibleTypes,
} from "./types";
import { compareActivities, dropDuplicateKeys } from "./grouping";
import {
  createLiveUpdates,
  type Subscribe,
  type Unsubscribe,
} from "./liveUpdates";
import { stripHtml } from "./utils";

interface ActivityPage {
  /** oldest first */
  activities: Activity[];
  /** cursor for the older page; null once the list has ended */
  next: string | null;
}

// One store per cache key: reopening a doc is instant, loaded pages survive remounts.
interface TimelineStore {
  doc: string;
  data: Ref<Activity[]>;
  loading: Ref<boolean>;
  error: Ref<unknown>;
  /** whether the newest page has ever landed */
  fetched: Ref<boolean>;
  /** the newest page was read for a mount still to come, so that mount needs no catch-up */
  prefetched: Ref<boolean>;
  next: Ref<string | null>;
  fetchingOlder: Ref<boolean>;
  load: () => Promise<void>;
  loadOlder: () => Promise<void>;
  /** one refetch however many callers ask; resolves when it lands */
  refresh: () => Promise<void>;
  subscribe: Subscribe;
}
const stores = new Map<string, TimelineStore>();

const PAGE_SIZE = 50;

// Unconfirmed rows per document. `renderKey` is the key a row was first drawn under;
// the server row adopts it, so Vue patches the node instead of remounting it.
type PendingRow = (Activity | CustomActivity) & {
  key: string;
  renderKey: string;
};
const pendingActivities = ref<Record<string, PendingRow[]>>({});

// All a retired pending row leaves behind: server key to render key, per document.
const adoptedKeys = ref<Record<string, Record<string, string>>>({});

const docKey = (doctype: string, docname: string) => `${doctype}:${docname}`;

const PENDING_KEY = "pending:";
const isUnresolved = (row: PendingRow) => row.key.startsWith(PENDING_KEY);

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
      fetchNextPage: store.loadOlder,
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

/**
 * Shows a row in the feed before the server has confirmed it. The row carries
 * `pending`, so the timeline renders it muted.
 */
export function addPendingActivity(
  doctype: string,
  docname: string,
  activity: Omit<Activity | CustomActivity, "key"> & { key?: string }
): PendingActivity {
  const doc = docKey(doctype, docname);
  const renderKey = activity.key ?? `${PENDING_KEY}${crypto.randomUUID()}`;
  const row = { ...activity, key: renderKey, renderKey, pending: true };
  setPendingRows(doc, (rows) => [...rows, row as PendingRow]);

  const resolve = (key: string, timestamp?: string) => {
    const confirmed = { key, pending: false, ...(timestamp ? { timestamp } : {}) };
    setPendingRows(doc, (rows) =>
      rows.map((r) =>
        r.renderKey === renderKey ? { ...r, ...confirmed } : r
      )
    );
    retireEverywhere(doc);
  };
  const drop = () =>
    setPendingRows(doc, (rows) =>
      rows.filter((r) => r.renderKey !== renderKey)
    );
  return { resolve, drop };
}

function getTimelineStore(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
): TimelineStore {
  const cacheKey = storeKey(doctype, docname, visibleTypes);
  let store = stores.get(cacheKey);
  if (!store) {
    store = createTimelineStore(doctype, docname, visibleTypes);
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

function createTimelineStore(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
): TimelineStore {
  const doc = docKey(doctype, docname);
  const data = ref<Activity[]>([]);
  const fetched = ref(false);
  const prefetched = ref(false);
  const next = ref<string | null>(null);
  const loading = ref(false);
  const error = ref<unknown>(null);
  const fetchingOlder = ref(false);

  // filtered server-side so the cursor walks only the rows this view shows
  const readPage = async (before?: string) => {
    const params = { types: visibleTypes, limit: PAGE_SIZE, before };
    const response = await getDocumentPart<ActivityPage>(
      doctype,
      docname,
      "activity",
      params
    );
    return response.data;
  };

  let inFlight: Promise<void> | undefined;
  const load = () => {
    if (inFlight) return inFlight;
    loading.value = true;
    inFlight = (async () => {
      try {
        const page = await readPage();
        data.value = mergeNewestPage(data.value, page);
        // the loaded rows run unbroken down to the held cursor, so a reload keeps it
        if (!fetched.value || page.next === null) next.value = page.next;
        error.value = null;
        fetched.value = true;
      } catch (failure) {
        error.value = failure;
      } finally {
        loading.value = false;
        inFlight = undefined;
      }
    })();
    return inFlight;
  };

  let olderInFlight: Promise<void> | undefined;
  const loadOlder = () => {
    if (olderInFlight) return olderInFlight;
    if (next.value === null) return Promise.resolve();
    fetchingOlder.value = true;
    olderInFlight = readPage(next.value)
      .then((page) => {
        data.value = prependOlder(data.value, page.activities);
        next.value = page.next;
      })
      .catch((failure) => {
        error.value = failure;
      })
      .finally(() => {
        fetchingOlder.value = false;
        olderInFlight = undefined;
      });
    return olderInFlight;
  };

  // sync: the feed and the rows drawn from it must not disagree for a render.
  watch(data, (feed) => retirePendingRows(doc, feed), { flush: "sync" });

  const refresh = debouncedRefresh(load, () => inFlight);
  const subscribe = createLiveUpdates(
    doctype,
    docname,
    { data, fetched, prefetched },
    typeNames(visibleTypes),
    refresh
  );
  return {
    doc,
    data,
    loading,
    error,
    fetched,
    prefetched,
    next,
    fetchingOlder,
    load,
    loadOlder,
    refresh,
    subscribe,
  };
}

/** Loaded rows older than the page stay; inside its span the server's answer wins. */
function mergeNewestPage(current: Activity[], page: ActivityPage): Activity[] {
  const oldest = page.activities[0];
  if (!oldest || page.next === null) return page.activities;
  const older = current.filter((a) => compareActivities(a, oldest) < 0);
  return [...older, ...page.activities];
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
  const adopted = adoptedKeys.value[store.doc] ?? {};
  const confirmed = dropDuplicateKeys(store.data.value).map((a) =>
    adopted[a.key] ? { ...a, renderKey: adopted[a.key] } : a
  );
  const waiting = (pendingActivities.value[store.doc] ?? []).filter(
    (row) => !types || types.includes(row.type)
  );
  return [...confirmed, ...waiting].sort(compareActivities);
}

function typeNames(visibleTypes?: VisibleTypes): string[] | undefined {
  return visibleTypes?.flatMap((t) =>
    typeof t === "string" ? [t] : Object.keys(t)
  );
}

function setPendingRows(
  doc: string,
  change: (rows: PendingRow[]) => PendingRow[]
) {
  pendingActivities.value = {
    ...pendingActivities.value,
    [doc]: change(pendingActivities.value[doc] ?? []),
  };
}

// a resolved row may already be in a feed: the socket can beat the request's answer
function retireEverywhere(doc: string) {
  for (const store of stores.values())
    if (store.doc === doc) retirePendingRows(doc, store.data.value);
}

/** Drops pending rows the server echoed back, keeping the key each rendered under. */
function retirePendingRows(doc: string, feed: Activity[]) {
  const rows = pendingActivities.value[doc];
  if (!rows?.length) return;

  const serverKeys = new Set(feed.map((a) => a.key));
  const keyByText = rows.some(isUnresolved) ? keysByText(feed) : undefined;
  const adopted: Record<string, string> = {};
  const waiting = rows.filter((row) => {
    const real = isUnresolved(row)
      ? keyByText?.get(rowText(row) ?? "")
      : row.key;
    if (!real || !serverKeys.has(real)) return true;
    adopted[real] = row.renderKey;
    return false;
  });
  if (waiting.length === rows.length) return;

  pendingActivities.value = { ...pendingActivities.value, [doc]: waiting };
  adoptedKeys.value = {
    ...adoptedKeys.value,
    [doc]: { ...adoptedKeys.value[doc], ...adopted },
  };
}

// A row with no key yet is matched on its text. An identical older row can swallow it.
function keysByText(feed: Activity[]): Map<string, string> {
  const keys = new Map<string, string>();
  for (const a of feed) {
    const text = rowText(a);
    if (text) keys.set(text, a.key);
  }
  return keys;
}

/** What a row says, for matching one the server echoed back under a key we don't know yet. */
function rowText(activity: Activity | CustomActivity) {
  const content = (activity.data as { content?: unknown } | null)?.content;
  if (typeof content !== "string") return undefined;
  const text = stripHtml(content).replace(/\s+/g, " ").trim();
  return text && JSON.stringify([activity.type, text]);
}
