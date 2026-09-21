import { computed, onMounted, onUnmounted, reactive, ref, type Ref } from "vue";
import { getDocumentPart } from "../../api";
import { getSocketInstance } from "../../socket";
import type { Activity, CustomActivity, Pagination, UserInfo } from "./types";
import { compareActivities, dropDuplicateKeys } from "./grouping";
import { getAssignee, stripHtml } from "./utils";

interface FeedPage {
  activities: Activity[];
  has_more_emails?: boolean;
  has_more_milestones?: boolean;
  next_milestone_start?: number;
}

// One store per cache key for the session, so reopening a doc is instant and
// paging state survives cached remounts.
interface TimelineStore {
  data: Ref<Activity[]>;
  loading: Ref<boolean>;
  error: Ref<unknown>;
  load: () => Promise<void>;
  // "older rows remain" per paged source, plus the backend-reported offset of
  // the next milestone page
  hasMoreEmails: Ref<boolean>;
  hasMoreMilestones: Ref<boolean>;
  milestoneStart: Ref<number>;
}
const stores = new Map<string, TimelineStore>();

/** e.g. ["email", "comment", { version: ["status", "priority"] }] */
export type VisibleTypes = Array<Activity["type"] | { version: string[] }>;

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

  const data = ref<Activity[]>([]);
  const loading = ref(false);
  const error = ref<unknown>(null);
  const hasMoreEmails = ref(true);
  const hasMoreMilestones = ref(false);
  const milestoneStart = ref(0);

  // On reload (e.g. a doc_update), re-append the older pages the user has already loaded.
  const load = async () => {
    loading.value = true;
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
    } catch (failure) {
      error.value = failure;
    } finally {
      loading.value = false;
    }
  };

  const store: TimelineStore = {
    data,
    loading,
    error,
    load,
    hasMoreEmails,
    hasMoreMilestones,
    milestoneStart,
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
  const visibleTypeNames = visibleTypes?.flatMap((t) =>
    typeof t === "string" ? [t] : Object.keys(t)
  );

  const store = getTimelineStore(doctype, docname, visibleTypes);

  subscribeToLiveUpdates(doctype, docname, store, visibleTypeNames);

  // deduped + sorted, but ungrouped: the component folds version runs at render
  // time, after the consumer's own filtering/merging
  const activities = computed<Array<Activity | CustomActivity>>(() => {
    const uniqueActivities = dropDuplicateKeys(store.data.value);
    uniqueActivities.sort(compareActivities);
    return uniqueActivities;
  });

  return {
    activities,
    loading: computed<boolean>(() => store.loading.value),
    error: computed<unknown>(() => store.error.value),
    reload: () => store.load(),
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

function subscribeToLiveUpdates(
  doctype: string,
  docname: string,
  store: TimelineStore,
  visibleTypes: string[] | undefined
) {
  const socket = getSocketInstance();
  if (!socket) return;

  // The socket payload has no avatar — reuse a resolved author from the feed, else fall back.
  const resolveAuthor = (email: string | undefined, fallback: UserInfo) => {
    if (!email) return fallback;
    const known = store.data.value.find((a) => a.author?.email === email)?.author;
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

    const current = store.data.value;
    if (action === "add") {
      store.data.value = [...current, activity];
    } else if (action === "delete") {
      store.data.value = current.filter((a) => a.key !== activity.key);
    } else {
      store.data.value = current.map((a) =>
        a.key === activity.key ? activity : a
      );
    }
  };

  const onDocUpdate = (payload: unknown) => {
    const { doctype: dt, name } = payload as { doctype: string; name: string };
    if (dt !== doctype || name !== docname) return;
    void store.load();
  };
  onMounted(() => {
    socket.emit("doc_subscribe", doctype, docname); // subscribes to doc updates for this doctype:docname
    socket.on("docinfo_update", onUpdate); // subscribes to live communications, comments, likes, assignments, attachments
    socket.on("doc_update", onDocUpdate); // subscribes to field changes
  });
  onUnmounted(() => {
    socket.emit("doc_unsubscribe", doctype, docname);
    socket.off("docinfo_update", onUpdate);
    socket.off("doc_update", onDocUpdate);
  });
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
