import { createResource } from "frappe-ui";
import { computed, onMounted, onUnmounted, reactive, ref, type Ref } from "vue";
import { getSocketInstance } from "../../socket";
import type { Activity, CustomActivity, Pagination, UserInfo } from "./types";
import { compareActivities, dropDuplicateKeys } from "./grouping";
import { getAssignee, stripHtml } from "./utils";

// One resource per doctype:docname for the session, so reopening a doc is instant.
const resources = new Map<string, ReturnType<typeof createResource>>();

// Paging state per source, kept outside the resource so it survives cached remounts: "older rows
// remain" for each, plus the offset the backend reports for the next milestone page.
const hasMoreEmailsByKey = new Map<string, Ref<boolean>>();
const hasMoreMilestonesByKey = new Map<string, Ref<boolean>>();
const milestoneStartByKey = new Map<string, Ref<number>>();

function pagingState<T>(
  states: Map<string, Ref<T>>,
  cacheKey: string,
  initial: T
): Ref<T> {
  let state = states.get(cacheKey);
  if (!state) {
    state = ref(initial) as Ref<T>;
    states.set(cacheKey, state);
  }
  return state;
}

/** e.g. ["email", "comment", { version: ["status", "priority"] }] */
export type VisibleTypes = Array<Activity["type"] | { version: string[] }>;

// filters are part of the cache identity
const timelineCacheKey = (
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
) =>
  `${doctype}:${docname}:${visibleTypes ? JSON.stringify(visibleTypes) : "*"}`;

function getTimelineResource(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
) {
  const cacheKey = timelineCacheKey(doctype, docname, visibleTypes);
  const existing = resources.get(cacheKey);
  if (existing) return existing;

  const hasMoreEmails = pagingState(hasMoreEmailsByKey, cacheKey, true);
  const hasMoreMilestones = pagingState(
    hasMoreMilestonesByKey,
    cacheKey,
    false
  );
  const milestoneStart = pagingState(milestoneStartByKey, cacheKey, 0);

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
  resources.set(cacheKey, resource);
  return resource;
}

/** Start (or reuse) the shared feed fetch without mounting anything; gate on `.fetched`. */
export function prefetchActivityTimeline(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
) {
  return getTimelineResource(doctype, docname, visibleTypes);
}

export function useActivityTimeline(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
) {
  const cacheKey = timelineCacheKey(doctype, docname, visibleTypes);
  const visibleTypeNames = visibleTypes?.flatMap((t) =>
    typeof t === "string" ? [t] : Object.keys(t)
  );

  const hasMoreEmails = pagingState(hasMoreEmailsByKey, cacheKey, true);
  const hasMoreMilestones = pagingState(
    hasMoreMilestonesByKey,
    cacheKey,
    false
  );
  const milestoneStart = pagingState(milestoneStartByKey, cacheKey, 0);

  const resource = getTimelineResource(doctype, docname, visibleTypes);

  subscribeToLiveUpdates(doctype, docname, resource, visibleTypeNames);

  // deduped + sorted, but ungrouped: the component folds version runs at render
  // time, after the consumer's own filtering/merging
  const activities = computed<Array<Activity | CustomActivity>>(() => {
    const fetched = (resource.data as Activity[] | undefined) ?? [];
    const uniqueActivities = dropDuplicateKeys(fetched);
    uniqueActivities.sort(compareActivities);
    return uniqueActivities;
  });

  return {
    activities,
    loading: computed<boolean>(() => resource.loading),
    reload: () => resource.reload(),
    paginate: createHistoryPagination(doctype, docname, resource, {
      hasMoreEmails,
      hasMoreMilestones,
      milestoneStart,
    }),
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
  resource: ReturnType<typeof createResource>,
  state: {
    hasMoreEmails: Ref<boolean>;
    hasMoreMilestones: Ref<boolean>;
    milestoneStart: Ref<number>;
  }
): Pagination {
  const append = (activities: Activity[]) => {
    const loaded = (resource.data as Activity[] | undefined) ?? [];
    resource.data = [...loaded, ...activities];
  };

  const olderEmails = createResource({
    url: "frappe.desk.form.activity.get_more_email_activities",
    auto: false,
    onSuccess: (res: { activities: Activity[]; has_more_emails?: boolean }) => {
      append(res.activities);
      state.hasMoreEmails.value = !!res.has_more_emails;
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
      state.hasMoreMilestones.value = !!res.has_more_milestones;
      // backend-supplied: a milestone on a field the user cannot read is counted but not
      // returned, so an offset counted from the rendered rows would skip the rows behind it
      state.milestoneStart.value =
        res.next_milestone_start ?? state.milestoneStart.value;
    },
  });

  const isFetching = () => olderEmails.loading || olderMilestones.loading;

  // One control, both sources: a row is older history whichever source it came from.
  const fetchNextPage = () => {
    if (isFetching()) return;
    if (state.hasMoreEmails.value) {
      const loaded = (resource.data as Activity[] | undefined) ?? [];
      // count-based offset: emails are only appended, so the loaded count is the next start
      const emailsLoaded = loaded.filter((a) => a.type === "email").length;
      olderEmails.submit({ doctype, name: docname, start: emailsLoaded });
    }
    if (state.hasMoreMilestones.value) {
      olderMilestones.submit({
        doctype,
        name: docname,
        start: state.milestoneStart.value,
      });
    }
  };

  // reactive() so the refs unwrap when read through the `paginate` prop.
  return reactive({
    hasNextPage: computed(
      () => state.hasMoreEmails.value || state.hasMoreMilestones.value
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
  resource: ReturnType<typeof createResource>,
  visibleTypes: string[] | undefined
) {
  const socket = getSocketInstance();
  if (!socket) return;

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
    resource.reload();
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
