import { createResource } from "frappe-ui";
import { computed, onMounted, onUnmounted, reactive, ref, type Ref } from "vue";
import { getSocketInstance } from "../../socket";
import type {
  Activity,
  CustomActivity,
  Pagination,
  UserInfo,
  VersionActivity,
  VersionChange,
} from "./types";
import { stripHtml } from "./utils";

// One resource per doctype:docname for the session, so reopening a doc is instant.
const resources = new Map<string, ReturnType<typeof createResource>>();

// "older emails remain" flag, kept outside the resource so it survives cached remounts.
const hasMoreEmailsByKey = new Map<string, Ref<boolean>>();

export function useActivityTimeline(
  doctype: string,
  docname: string,
  paginate?: boolean
) {
  const cacheKey = `${doctype}:${docname}`;

  let hasMoreEmails = hasMoreEmailsByKey.get(cacheKey);
  if (!hasMoreEmails) {
    hasMoreEmails = ref(true);
    hasMoreEmailsByKey.set(cacheKey, hasMoreEmails);
  }

  let resource = resources.get(cacheKey);
  if (!resource) {
    resource = createResource({
      url: "frappe.desk.form.activity.get_activity_timeline",
      params: { doctype, name: docname },
      cache: `activities:${cacheKey}`,
      auto: true,
      // transform only sets resource.data; onSuccess still sees the raw response,
      // so has_more_emails is read there (not from transform's output).
      transform: (res: { activities: Activity[] }) => res.activities,
      onSuccess: (res: { has_more_emails?: boolean }) => {
        hasMoreEmails!.value = !!res.has_more_emails;
      },
    });
    resources.set(cacheKey, resource);
  }

  subscribeToLiveUpdates(doctype, docname, resource);

  return {
    activities: computed<Array<Activity | CustomActivity>>(() => {
      const fetched = (resource.data as Activity[] | undefined) ?? [];
      const uniqueActivities = dropDuplicateKeys(fetched);
      uniqueActivities.sort(compareActivities);
      const grouped = groupVersionActivities(uniqueActivities);

      // If pagination true, inject a Load More row above the oldest email, to show "Load More" button. If no more emails, don't inject.
      if (!paginate || !hasMoreEmails!.value) return grouped;
      const oldestEmailIdx = grouped.findIndex((a) => a.type === "email");
      if (oldestEmailIdx === -1) return grouped;
      const loadMore: CustomActivity = {
        type: "load_more",
        key: "load-more",
        timestamp: grouped[oldestEmailIdx].timestamp,
        data: null,
      };
      return [
        ...grouped.slice(0, oldestEmailIdx),
        loadMore,
        ...grouped.slice(oldestEmailIdx),
      ];
    }),
    loading: computed<boolean>(() => resource.loading),
    error: computed(() => resource.error || null),
    reload: () => resource.reload(),
    paginate: paginate
      ? createEmailPagination(doctype, docname, resource, hasMoreEmails)
      : undefined,
  };
}

// Email paging: fetch the next older page and append; the activities computed re-sorts.
function createEmailPagination(
  doctype: string,
  docname: string,
  resource: ReturnType<typeof createResource>,
  hasMoreEmails: Ref<boolean>
): Pagination {
  const olderEmails = createResource({
    url: "frappe.desk.form.activity.get_more_email_activities",
    auto: false,
    onSuccess: (res: { activities: Activity[]; has_more_emails?: boolean }) => {
      const loaded = (resource.data as Activity[] | undefined) ?? [];
      resource.data = [...loaded, ...res.activities];
      hasMoreEmails.value = !!res.has_more_emails;
    },
  });

  const fetchNextPage = () => {
    if (olderEmails.loading || !hasMoreEmails.value) return;
    const loaded = (resource.data as Activity[] | undefined) ?? [];
    // count-based offset: emails are only appended, so the loaded count is the next start
    const emailsLoaded = loaded.filter((a) => a.type === "email").length;
    olderEmails.submit({ doctype, name: docname, start: emailsLoaded });
  };

  // reactive() so the refs unwrap when read through the `paginate` prop.
  return reactive({
    hasNextPage: computed(() => hasMoreEmails.value),
    isFetchingNextPage: computed(() => olderEmails.loading),
    fetchNextPage,
  });
}

function subscribeToLiveUpdates(
  doctype: string,
  docname: string,
  resource: ReturnType<typeof createResource>
) {
  const socket = getSocketInstance();

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
    const activity = normalizeLiveActivity(key, doc, resolveAuthor);
    if (!activity) return;

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

  onMounted(() => {
    socket?.emit("doc_subscribe", doctype, docname);
    socket?.on("docinfo_update", onUpdate);
  });
  onUnmounted(() => {
    socket?.emit("doc_unsubscribe", doctype, docname);
    socket?.off("docinfo_update", onUpdate);
  });
}

// Client mirror of the backend normalizers for the realtime socket payload. Only
// realtime-publishing keys are handled; the rest arrive on the next reload.
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
          icon: "heart",
          text: `${author.fullname} liked`,
        },
      };

    case "assignment_logs": {
      const isCompleted = doc.comment_type === "Assignment Completed";
      return {
        type: "log",
        key: `log:${name}`,
        timestamp,
        author,
        data: {
          name,
          subtype: isCompleted ? "assignment_completed" : "assigned",
          icon: isCompleted ? "circle-check" : "user-plus",
          text: stripHtml(String(doc.content ?? "")),
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

function dropDuplicateKeys(activities: Activity[]): Activity[] {
  const uniqueActivities = new Set<string>();
  return activities.filter((a) =>
    uniqueActivities.has(a.key) ? false : uniqueActivities.add(a.key)
  );
}

function compareActivities(
  a: Pick<Activity, "timestamp" | "key">,
  b: Pick<Activity, "timestamp" | "key">
): number {
  return (
    timeValue(a.timestamp) - timeValue(b.timestamp) ||
    a.key.localeCompare(b.key)
  );
}

// Frappe timestamps use a space separator; Date.parse needs 'T' for reliable parsing.
function timeValue(ts?: string): number {
  if (!ts) return 0;
  const t = Date.parse(ts.includes(" ") ? ts.replace(" ", "T") : ts);
  return Number.isNaN(t) ? 0 : t;
}

// Fold each run of consecutive same-author version rows into one summary; others pass through.
export function groupVersionActivities(activities: Activity[]): Activity[] {
  const out: Activity[] = [];
  let runStart = 0;
  while (runStart < activities.length) {
    const first = activities[runStart];
    if (first.type !== "version") {
      out.push(first);
      runStart++;
      continue;
    }
    let runEnd = runStart + 1;
    while (
      runEnd < activities.length &&
      activities[runEnd].type === "version" &&
      activities[runEnd].author?.fullname === first.author?.fullname
    ) {
      runEnd++;
    }
    const summary = summarizeVersions(
      activities.slice(runStart, runEnd) as VersionActivity[]
    );
    if (summary) out.push(summary);
    runStart = runEnd;
  }
  return out;
}

// Collapse a run's changes into one summary row carrying a `group` of net changes;
// e.g. status Open→InProgress→Closed becomes status Open→Closed (with full history).
function summarizeVersions(
  versions: VersionActivity[]
): VersionActivity | null {
  const changes: VersionChange[] = []; // one net change per field, in first-seen order
  const byField = new Map<string, { change: VersionChange; index: number }>();

  for (const row of versions) {
    const change = row.data;
    // doc-level rows have no fieldname — never collapse
    if (!change.fieldname) {
      changes.push({ ...change });
      continue;
    }

    const seen = byField.get(change.fieldname);
    if (!seen) {
      const seeded: VersionChange =
        change.type === "diff"
          ? {
              ...change,
              history: [
                {
                  from: change.from ?? "",
                  to: change.to,
                  timestamp: row.timestamp,
                },
              ],
            }
          : { ...change };
      byField.set(change.fieldname, { change: seeded, index: changes.length });
      changes.push(seeded);
    } else if (seen.change.type === "diff" && change.type === "diff") {
      // advance the net "to" (keep the first row's "from") and record the hop
      seen.change.to = change.to;
      seen.change.history = [
        ...(seen.change.history ?? []),
        { from: change.from ?? "", to: change.to, timestamp: row.timestamp },
      ];
    } else {
      // type changed mid-run (e.g. value edited then cleared) — take the latest
      const replacement: VersionChange = { ...change };
      changes[seen.index] = replacement;
      byField.set(change.fieldname, { change: replacement, index: seen.index });
    }
  }

  // drop fields that churned back to their starting value (net no-op)
  const visible = changes.filter(
    (c) => !(c.type === "diff" && c.from === c.to)
  );
  if (visible.length === 0) return null;

  // key off the first row so Vue reuses the item (keeps expanded state); timestamp from last
  const first = versions[0];
  const last = versions[versions.length - 1];
  const data =
    visible.length === 1
      ? { ...visible[0] }
      : { ...visible[0], group: visible };
  return { ...last, key: first.key, data };
}
