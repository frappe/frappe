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
import { getSocketInstance, subscribeToDoc } from "../../socket";
import type {
  Activity,
  CustomActivity,
  Pagination,
  PendingActivity,
  UserInfo,
  VisibleTypes,
} from "./types";
import { compareActivities, dropDuplicateKeys } from "./grouping";
import { getAssignee, stripHtml } from "./utils";

// One store per cache key for the session, so reopening a doc is instant and
// paging state survives cached remounts.
interface TimelineStore {
  resource: ReturnType<typeof createResource>;
  // "older rows remain" per paged source, plus the backend-reported offset of
  // the next milestone page
  hasMoreEmails: Ref<boolean>;
  hasMoreMilestones: Ref<boolean>;
  milestoneStart: Ref<number>;
  /** one refetch however many callers ask; resolves when it lands */
  refresh: () => Promise<void>;
  /** start listening to the doc; call the result to stop */
  subscribe: () => () => void;
}
const stores = new Map<string, TimelineStore>();

// Rows shown before the server confirmed them. Keyed by document, not cache key,
// so every filtered view of that doc shows them. `key` is the row's identity for
// the whole of its life and never changes; `confirmedKey` is what it waits for.
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
 * Drops pending rows the server has echoed back, keeping the key each rendered under.
 * The real row then takes that key, so Vue patches the node the pending row mounted
 * rather than replacing it — replacing it rebuilds the email iframe, which comes back
 * at its collapsed height and jumps.
 */
function retirePendingRows(doctype: string, docname: string, feed: Activity[]) {
  const doc = docKey(doctype, docname);
  const rows = pendingActivities.value[doc];
  if (!rows?.length) return;

  const confirmedKeys = new Set(feed.map((a) => a.key));
  // The socket can deliver the real row before the request that created it answers, so a
  // row with no key to wait for yet is matched on what it says. An identical older row
  // can swallow it, which only costs it the wait until the next fetch.
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
    // transform sets resource.data; onSuccess still sees the raw response, so the
    // has_more_* flags are read there (not from transform's output). On reload
    // (e.g. a doc_update), re-append the older pages the user has already loaded.
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
  let unsubscribe: (() => void) | undefined;
  onMounted(() => {
    unsubscribe = store.subscribe();
  });
  onUnmounted(() => {
    unsubscribe?.();
    unsubscribe = undefined;
  });

  // deduped + sorted, but ungrouped: the component folds version runs at render
  // time, after the consumer's own filtering/merging
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

/** Returns subscribe(): the first caller wires the socket, the last unwires it. */
function createLiveUpdates(
  doctype: string,
  docname: string,
  resource: ReturnType<typeof createResource>,
  visibleTypes: string[] | undefined,
  refresh: () => Promise<void>
): () => () => void {
  const socket = getSocketInstance();
  if (!socket) return () => () => {};

  // The socket payload has no avatar — reuse a resolved author from the feed, else fall back.
  const resolveAuthor = (email: string | undefined, fallback: UserInfo) => {
    if (!email) return fallback;
    const known = ((resource.data as Activity[] | undefined) ?? []).find(
      (a) => a.author?.email === email
    )?.author;
    return known ?? fallback;
  };

  const onUpdate = (payload: unknown) => {
    const { doc, key, action } = payload as {
      doc: Record<string, unknown>;
      key: string;
      action: "add" | "update" | "delete";
    };
    if (doc.reference_doctype !== doctype || doc.reference_name !== docname)
      return;

    const activity = normalizeLiveActivity(key, doc, resolveAuthor);
    if (!activity) return;
    // mirror the server-side visibleTypes filter
    if (visibleTypes && !visibleTypes.includes(activity.type)) return;

    const current = (resource.data as Activity[] | undefined) ?? [];
    if (action === "add") {
      resource.data = [...current, activity];
    } else if (action === "delete") {
      resource.data = current.filter((a) => a.key !== activity.key);
    } else {
      resource.data = current.map((a) =>
        a.key === activity.key ? activity : a
      );
    }
  };

  const onDocUpdate = (payload: unknown) => {
    const { doctype: dt, name } = payload as { doctype: string; name: string };
    if (dt !== doctype || name !== docname) return;
    refresh();
  };

  // A reconnect gives us a new socket, so whatever was sent meanwhile is gone and the
  // feed has to catch up. Rejoining the rooms is the socket module's own job.
  // `connect` also fires on the very first connect, so only act after a drop.
  let dropped = false;
  const onDisconnect = () => {
    dropped = true;
  };
  const onConnect = () => {
    if (!dropped) return;
    dropped = false;
    refresh();
  };

  const handlers: Record<string, (...args: unknown[]) => void> = {
    docinfo_update: onUpdate, // comments, emails, likes, assignments, attachments
    doc_update: onDocUpdate, // field changes
    disconnect: onDisconnect,
    connect: onConnect,
  };

  let subscribers = 0;
  let leaveRoom: (() => void) | undefined;

  return function subscribe() {
    if (++subscribers === 1) {
      leaveRoom = subscribeToDoc(socket, doctype, docname);
      for (const event in handlers) socket.on(event, handlers[event]);
      // nobody was listening while this was closed, so the feed may have moved
      if (resource.fetched) refresh();
    }

    let stopped = false;
    return function unsubscribe() {
      if (stopped) return;
      stopped = true;
      if (--subscribers > 0) return;
      leaveRoom?.();
      leaveRoom = undefined;
      for (const event in handlers) socket.off(event, handlers[event]);
    };
  };
}

// (assignee bolding is backend-supplied, so live assignment rows bold only the actor.)
function normalizeLiveActivity(
  key: string,
  doc: Record<string, unknown>,
  resolveAuthor: (email: string | undefined, fallback: UserInfo) => UserInfo
): Activity | null {
  const timestamp = String(doc.creation);
  const actorEmail = (doc.comment_email as string) || (doc.owner as string);
  const author = resolveAuthor(actorEmail, {
    email: actorEmail,
    fullname: (doc.comment_by as string) || actorEmail,
  });
  const name = doc.name as string;

  switch (key) {
    case "comments":
      return {
        type: "comment",
        key: `comment:${name}`,
        timestamp,
        author,
        data: { name, content: doc.content as string },
      };

    case "like_logs":
      return {
        type: "log",
        key: `log:${name}`,
        timestamp,
        author,
        data: {
          name,
          subtype: "like",
          text: `${author.fullname} liked`,
        },
      };

    case "assignment_logs": {
      const isCompleted = doc.comment_type === "Assignment Completed";
      const text = stripHtml(String(doc.content ?? ""));
      // mirror the backend so the assignee bolds on live rows too (not just the actor)
      const assignee = getAssignee(text, String(doc.comment_type ?? ""));
      return {
        type: "log",
        key: `log:${name}`,
        timestamp,
        author,
        data: {
          name,
          subtype: isCompleted ? "assignment_completed" : "assigned",
          text,
          // additive, like the backend: only present when an assignee was found
          ...(assignee ? { assignee } : {}),
        },
      };
    }

    case "attachment_logs": {
      const isRemoved = doc.comment_type === "Attachment Removed";
      const content = String(doc.content ?? "");
      const href = content.match(/href=['"]([^'"]+)['"]/);
      const fileUrl = !isRemoved && href ? href[1] : undefined;
      return {
        type: "attachment_log",
        key: `attachment:${name}`,
        timestamp,
        author,
        data: {
          name,
          action: isRemoved ? "removed" : "added",
          fileName: stripHtml(content),
          // private files live under /private/… — stabler than the `fa-lock` icon
          isPrivate: fileUrl?.startsWith("/private/") ?? false,
          ...(fileUrl ? { fileUrl } : {}),
        },
      };
    }

    case "communications":
      return {
        type: "email",
        key: `email:${name}`,
        timestamp: String(doc.communication_date || doc.creation),
        author: resolveAuthor(doc.sender as string, {
          email: doc.sender as string,
          fullname: (doc.sender_full_name || doc.sender) as string,
        }),
        data: {
          name,
          subject: doc.subject as string,
          sender: doc.sender as string,
          to: doc.recipients as string,
          cc: doc.cc as string,
          bcc: doc.bcc as string,
          content: doc.content as string,
          deliveryStatus: doc.delivery_status as string,
          attachments: [],
        },
      };

    default:
      return null;
  }
}
