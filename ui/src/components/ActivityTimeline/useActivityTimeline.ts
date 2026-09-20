import { createResource } from "frappe-ui";
import {
  computed,
  onMounted,
  onUnmounted,
  reactive,
  ref,
  watch,
  type Ref,
} from "vue";
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

// One store per cache key: reopening a doc is instant, paging state survives remounts.
interface TimelineStore {
  resource: ReturnType<typeof createResource>;
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

  const hasMoreEmails = ref(true);
  const hasMoreMilestones = ref(false);
  const milestoneStart = ref(0);

  const resource: ReturnType<typeof createResource> = createResource({
    url: "frappe.desk.form.activity.get_activity_timeline",
    // filtered server-side so pagination math stays correct
    params: { doctype, name: docname, visible_types: visibleTypes },
    cache: `activities:${cacheKey}`,
    auto: true,
    // transform sets resource.data, onSuccess sees the raw response, so the has_more_*
    // flags are read there. On reload, re-append the older pages already loaded.
    transform: (res: { activities: Activity[] }) => {
      const oldActivities = (resource.data as Activity[] | undefined) ?? [];

      const newActivities = res.activities;
      const newActivityKeys = new Set(newActivities.map((a) => a.key));

      const paginatedOlderRows = oldActivities.filter(
        (a) => isPagedRow(a) && !newActivityKeys.has(a.key)
      );
      return [...newActivities, ...paginatedOlderRows];
    },
    onSuccess: (res: {
      has_more_emails?: boolean;
      has_more_milestones?: boolean;
      next_milestone_start?: number;
    }) => {
      hasMoreEmails.value = !!res.has_more_emails;
      // This response only carries the first milestone page. Once the user has paged past it
      // the transform above keeps those older rows, so page one's flag and offset are stale.
      if (milestoneStart.value === 0) {
        hasMoreMilestones.value = !!res.has_more_milestones;
        milestoneStart.value = res.next_milestone_start ?? 0;
      }
    },
  });

  // sync: the feed and the rows drawn from it must not disagree for a render.
  watch(
    () => resource.data,
    (feed) => retirePendingRows(doctype, docname, (feed as Activity[]) ?? []),
    { flush: "sync" }
  );

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
        if (resource.loading) await resource.promise?.catch(() => {});
        // the window is closed, so everything in it is covered by the fetch below
        changedSinceFetch = false;
        await resource.reload();
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
    resource,
    hasMoreEmails,
    hasMoreMilestones,
    milestoneStart,
    refresh,
    subscribe: createLiveUpdates(
      doctype,
      docname,
      resource,
      visibleTypeNames,
      refresh
    ),
  };
  stores.set(cacheKey, store);
  return store;
}

export function useActivityTimeline(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
) {
  const store = getTimelineStore(doctype, docname, visibleTypes);
  const { resource } = store;

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
    const confirmed = dropDuplicateKeys(
      (resource.data as Activity[] | undefined) ?? []
    );
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
    loading: computed<boolean>(() => resource.loading),
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
  const { resource } = store;
  const append = (activities: Activity[]) => {
    const loaded = (resource.data as Activity[] | undefined) ?? [];
    resource.data = [...loaded, ...activities];
  };

  const olderEmails = createResource({
    url: "frappe.desk.form.activity.get_more_email_activities",
    auto: false,
    onSuccess: (res: { activities: Activity[]; has_more_emails?: boolean }) => {
      append(res.activities);
      store.hasMoreEmails.value = !!res.has_more_emails;
    },
  });

  const olderMilestones = createResource({
    url: "frappe.desk.form.activity.get_more_milestone_activities",
    auto: false,
    onSuccess: (res: {
      activities: Activity[];
      has_more_milestones?: boolean;
      next_milestone_start?: number;
    }) => {
      append(res.activities);
      store.hasMoreMilestones.value = !!res.has_more_milestones;
      // backend-supplied: a milestone on a field the user cannot read is counted but not
      // returned, so an offset counted from the rendered rows would skip the rows behind it
      store.milestoneStart.value =
        res.next_milestone_start ?? store.milestoneStart.value;
    },
  });

  const isFetching = () => olderEmails.loading || olderMilestones.loading;

  // One control, both sources: a row is older history whichever source it came from.
  const fetchNextPage = () => {
    if (isFetching()) return;
    if (store.hasMoreEmails.value) {
      const loaded = (resource.data as Activity[] | undefined) ?? [];
      // count-based offset: emails are only appended, so the loaded count is the next start
      const emailsLoaded = loaded.filter((a) => a.type === "email").length;
      olderEmails.submit({ doctype, name: docname, start: emailsLoaded });
    }
    if (store.hasMoreMilestones.value) {
      olderMilestones.submit({
        doctype,
        name: docname,
        start: store.milestoneStart.value,
      });
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
