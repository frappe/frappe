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
  Pagination,
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

interface FeedPage {
  activities: Activity[];
  has_more_emails?: boolean;
  has_more_milestones?: boolean;
  next_milestone_start?: number;
}

// One store per cache key: reopening a doc is instant, paging state survives remounts.
interface TimelineStore {
  data: Ref<Activity[]>;
  loading: Ref<boolean>;
  error: Ref<unknown>;
  /** whether the first page has ever landed */
  fetched: Ref<boolean>;
  load: () => Promise<void>;
  // "older rows remain" per paged source, plus the next milestone page's offset
  hasMoreEmails: Ref<boolean>;
  hasMoreMilestones: Ref<boolean>;
  milestoneStart: Ref<number>;
  /** one refetch however many callers ask; resolves when it lands */
  refresh: () => Promise<void>;
  subscribe: Subscribe;
}
const stores = new Map<string, TimelineStore>();

// Rows shown before the server confirmed them, keyed by document so every filtered
// view of it shows them. `key` never changes; `confirmedKey` is what the row waits for.
type PendingRow = (Activity | CustomActivity) & {
  key: string;
  confirmedKey?: string;
};
const pendingActivities = ref<Record<string, PendingRow[]>>({});

// All a retired pending row leaves behind: the key it rendered under, per document.
const adoptedKeys = ref<Record<string, Record<string, string>>>({});

const docKey = (doctype: string, docname: string) => `${doctype}:${docname}`;

const PENDING_KEY = "pending:";
const isUnresolved = (row: PendingRow) =>
  !row.confirmedKey && row.key.startsWith(PENDING_KEY);

/** What a row says, for matching one the server echoed back under a key we don't know yet. */
const rowText = (activity: Activity | CustomActivity) => {
  const content = (activity.data as { content?: unknown } | null)?.content;
  if (typeof content !== "string") return undefined;
  const text = stripHtml(content).replace(/\s+/g, " ").trim();
  return text && JSON.stringify([activity.type, text]);
};

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
  const key = activity.key ?? `${PENDING_KEY}${crypto.randomUUID()}`;

  const setRows = (next: (rows: PendingRow[]) => PendingRow[]) => {
    pendingActivities.value = {
      ...pendingActivities.value,
      [doc]: next(pendingActivities.value[doc] ?? []),
    };
  };

  setRows((rows) => [
    ...rows,
    { ...activity, key, pending: true } as PendingRow,
  ]);

  return {
    resolve: (confirmedKey: string) =>
      setRows((rows) =>
        rows.map((r) => (r.key === key ? { ...r, confirmedKey } : r))
      ),
    drop: () => setRows((rows) => rows.filter((r) => r.key !== key)),
  };
}

/**
 * Drops pending rows the server echoed back, keeping the key each rendered under so the
 * real row adopts it. Vue then patches that node rather than remounting it, which would
 * rebuild the email iframe at its collapsed height and jump.
 */
function retirePendingRows(doctype: string, docname: string, feed: Activity[]) {
  const doc = docKey(doctype, docname);
  const rows = pendingActivities.value[doc];
  if (!rows?.length) return;

  const confirmedKeys = new Set(feed.map((a) => a.key));
  // The socket can deliver the real row before the request answers, so a row with no key
  // yet is matched on its text. An identical older row can swallow it, costing one fetch.
  const keyByText = new Map<string, string>();
  if (rows.some(isUnresolved))
    for (const a of feed) {
      const text = rowText(a);
      if (text) keyByText.set(text, a.key);
    }

  const adopted: Record<string, string> = {};
  const waiting = rows.filter((row) => {
    const real =
      row.confirmedKey ??
      (isUnresolved(row) ? keyByText.get(rowText(row) ?? "") : row.key);
    if (!real || !confirmedKeys.has(real)) return true;
    adopted[real] = row.key;
    return false;
  });
  if (waiting.length === rows.length) return;

  pendingActivities.value = { ...pendingActivities.value, [doc]: waiting };
  adoptedKeys.value = {
    ...adoptedKeys.value,
    [doc]: { ...adoptedKeys.value[doc], ...adopted },
  };
}

// one save can fire several doc_updates: wait a moment, then fetch once
const REFRESH_DEBOUNCE_MS = 300;

// filters are part of the cache identity
const timelineCacheKey = (
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
) =>
  `${doctype}:${docname}:${visibleTypes ? JSON.stringify(visibleTypes) : "*"}`;

function getTimelineStore(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
): TimelineStore {
  const cacheKey = timelineCacheKey(doctype, docname, visibleTypes);
  const existing = stores.get(cacheKey);
  if (existing) return existing;

  const visibleTypeNames = visibleTypes?.flatMap((t) =>
    typeof t === "string" ? [t] : Object.keys(t)
  );

  const data = ref<Activity[]>([]);
  const loading = ref(false);
  const error = ref<unknown>(null);
  const fetched = ref(false);
  const hasMoreEmails = ref(true);
  const hasMoreMilestones = ref(false);
  const milestoneStart = ref(0);

  // On reload (e.g. a doc_update), re-append the older pages the user has already loaded.
  let inFlight: Promise<void> | undefined;
  const load = () => {
    if (inFlight) return inFlight;
    loading.value = true;
    inFlight = (async () => {
      try {
        // filtered server-side so pagination math stays correct
        const { data: page } = await getDocumentPart<FeedPage>(doctype, docname, "activity", {
          types: visibleTypes,
        });
        const newActivityKeys = new Set(page.activities.map((a) => a.key));
        const paginatedOlderRows = data.value.filter(
          (a) => isPagedRow(a) && !newActivityKeys.has(a.key)
        );
        data.value = [...page.activities, ...paginatedOlderRows];
        hasMoreEmails.value = !!page.has_more_emails;
        // This response only carries the first milestone page. Once the user has paged past it
        // the rows above are kept, so page one's flag and offset are stale.
        if (milestoneStart.value === 0) {
          hasMoreMilestones.value = !!page.has_more_milestones;
          milestoneStart.value = page.next_milestone_start ?? 0;
        }
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

  // sync: the feed and the rows drawn from it must not disagree for a render.
  watch(data, (feed) => retirePendingRows(doctype, docname, feed), {
    flush: "sync",
  });

  // Every trigger in the window joins the same fetch, so one save costs one request.
  let pendingRefresh: Promise<void> | undefined;
  let changedSinceFetch = false;
  const refresh = (): Promise<void> => {
    if (pendingRefresh) {
      changedSinceFetch = true;
      return pendingRefresh;
    }
    pendingRefresh = (async () => {
      do {
        await new Promise((done) => setTimeout(done, REFRESH_DEBOUNCE_MS));
        // a fetch already running was sent before the change, so it may miss it
        if (inFlight) await inFlight.catch(() => {});
        // the window is closed, so everything in it is covered by the fetch below
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

  const store: TimelineStore = {
    data,
    loading,
    error,
    fetched,
    load,
    hasMoreEmails,
    hasMoreMilestones,
    milestoneStart,
    refresh,
    subscribe: createLiveUpdates(
      doctype,
      docname,
      { data, fetched },
      visibleTypeNames,
      refresh
    ),
  };
  stores.set(cacheKey, store);
  void load();
  return store;
}

export function useActivityTimeline(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
) {
  const store = getTimelineStore(doctype, docname, visibleTypes);

  // the store is shared, so one socket serves every consumer of it
  let unsubscribe: Unsubscribe | undefined;
  onMounted(() => {
    unsubscribe = store.subscribe();
  });
  onUnmounted(() => {
    unsubscribe?.();
    unsubscribe = undefined;
  });

  // deduped + sorted but ungrouped; the component folds version runs at render time
  const activities = computed<Array<Activity | CustomActivity>>(() => {
    const confirmed = dropDuplicateKeys(store.data.value);
    const doc = docKey(doctype, docname);
    const adopted = adoptedKeys.value[doc];
    const shown = adopted
      ? confirmed.map((a) =>
          adopted[a.key] ? { ...a, key: adopted[a.key] } : a
        )
      : confirmed;
    const waiting = pendingActivities.value[doc] ?? [];
    return [...shown, ...waiting].sort(compareActivities);
  });

  return {
    activities,
    loading: computed<boolean>(() => store.loading.value),
    error: computed<unknown>(() => store.error.value),
    reload: () => store.refresh(),
    paginate: createHistoryPagination(doctype, docname, store),
  };
}

// The two paged sources; everything else in the feed arrives whole on the first load.
function isPagedRow(activity: Activity | CustomActivity): boolean {
  if (activity.type === "email") return true;
  if (activity.type !== "log") return false;
  return (
    (activity.data as { subtype?: string } | null)?.subtype === "milestone"
  );
}

// History paging: fetch the next older page of each paged source and append; activities re-sorts.
function createHistoryPagination(
  doctype: string,
  docname: string,
  store: TimelineStore
): Pagination {
  const append = (activities: Activity[]) => {
    store.data.value = [...store.data.value, ...activities];
  };

  const fetchingEmails = ref(false);
  const fetchingMilestones = ref(false);

  const olderEmails = async (start: number) => {
    fetchingEmails.value = true;
    try {
      const { data: page } = await getDocumentPart<FeedPage>(doctype, docname, "activity", {
        stream: "emails",
        start,
      });
      append(page.activities);
      store.hasMoreEmails.value = !!page.has_more_emails;
    } catch (failure) {
      store.error.value = failure;
    } finally {
      fetchingEmails.value = false;
    }
  };

  const olderMilestones = async (start: number) => {
    fetchingMilestones.value = true;
    try {
      const { data: page } = await getDocumentPart<FeedPage>(doctype, docname, "activity", {
        stream: "milestones",
        start,
      });
      append(page.activities);
      store.hasMoreMilestones.value = !!page.has_more_milestones;
      // backend-supplied: a milestone on a field the user cannot read is counted but not
      // returned, so an offset counted from the rendered rows would skip the rows behind it
      store.milestoneStart.value =
        page.next_milestone_start ?? store.milestoneStart.value;
    } catch (failure) {
      store.error.value = failure;
    } finally {
      fetchingMilestones.value = false;
    }
  };

  const isFetching = () => fetchingEmails.value || fetchingMilestones.value;

  // One control, both sources: a row is older history whichever source it came from.
  const fetchNextPage = () => {
    if (isFetching()) return;
    if (store.hasMoreEmails.value) {
      // count-based offset: emails are only appended, so the loaded count is the next start
      const emailsLoaded = store.data.value.filter((a) => a.type === "email").length;
      void olderEmails(emailsLoaded);
    }
    if (store.hasMoreMilestones.value) {
      void olderMilestones(store.milestoneStart.value);
    }
  };

  // reactive() so the refs unwrap when read through the `paginate` prop.
  return reactive({
    hasNextPage: computed(
      () => store.hasMoreEmails.value || store.hasMoreMilestones.value
    ),
    isFetchingNextPage: computed(() => isFetching()),
    fetchNextPage,
    isPagedRow,
    // in-feed row above the oldest paged row; the copy lives here, not in the component
    loadMore: {
      position: "inline" as const,
      label: "Show previous activity",
      icon: "lucide-chevrons-up",
    },
  });
}
