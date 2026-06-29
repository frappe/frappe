import { createResource } from "frappe-ui";
import { computed, onMounted, onUnmounted, reactive, ref, type Ref } from "vue";
import { getSocketInstance } from "../../socket";
import type {
  Activity,
  CustomActivity,
  UserInfo,
  VersionActivity,
  VersionChange,
} from "./types";

const resources = new Map<string, ReturnType<typeof createResource>>();
// "older emails remain" flag, kept outside the resource so it survives cached remounts.
const hasMoreEmailsByKey = new Map<string, Ref<boolean>>();

export function useActivityTimeline(
  doctype: string,
  docname: string,
  paginate?: boolean
) {
  const key = `${doctype}:${docname}`;

  let hasMoreEmails = hasMoreEmailsByKey.get(key);
  if (!hasMoreEmails) {
    hasMoreEmails = ref(true);
    hasMoreEmailsByKey.set(key, hasMoreEmails);
  }

  let resource = resources.get(key);
  if (!resource) {
    resource = createResource({
      url: "frappe.desk.form.activity.get_activity_timeline",
      params: { doctype, name: docname },
      cache: `activities:${key}`,
      auto: true,
      transform: (res: { activities: Activity[] }) => res.activities,
      onSuccess: (res: { has_more_emails?: boolean }) => {
        hasMoreEmails!.value = !!res.has_more_emails;
      },
    });
    resources.set(key, resource);
  }

  handleLiveUpdates(doctype, docname, resource);

  return {
    activities: computed<Array<Activity | CustomActivity>>(() => {
      const base = (resource.data as Activity[] | undefined) ?? [];
      const merged = dropDuplicateKeys(base);
      merged.sort(compareActivities);
      const list = groupVersionActivities(merged);

      // Inject the "Load More" row above the oldest email
      if (!paginate || !hasMoreEmails!.value) return list;
      const oldestEmailIdx = list.findIndex((a) => a.type === "email");
      if (oldestEmailIdx === -1) return list;
      const loadMore: CustomActivity = {
        type: "load_more",
        key: "load-more",
        timestamp: list[oldestEmailIdx].timestamp,
        data: null,
      };
      return [
        ...list.slice(0, oldestEmailIdx),
        loadMore,
        ...list.slice(oldestEmailIdx),
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
) {
  const moreResource = createResource({
    url: "frappe.desk.form.activity.get_more_email_activities",
    auto: false,
    onSuccess: (res: { activities: Activity[]; has_more_emails?: boolean }) => {
      const current = (resource.data as Activity[] | undefined) ?? [];
      resource.data = [...current, ...res.activities];
      hasMoreEmails.value = !!res.has_more_emails;
    },
  });

  const fetchNextPage = () => {
    if (moreResource.loading || !hasMoreEmails.value) return;
    const emailsLoaded = (
      (resource.data as Activity[] | undefined) ?? []
    ).filter((a) => a.type === "email").length;
    moreResource.submit({ doctype, name: docname, start: emailsLoaded });
  };

  // reactive() so refs unwrap through the `paginate` prop (Vue won't unwrap nested refs).
  return reactive({
    hasNextPage: computed(() => hasMoreEmails.value),
    isFetchingNextPage: computed(() => moreResource.loading),
    fetchNextPage,
  });
}

function handleLiveUpdates(
  doctype: string,
  docname: string,
  resource: ReturnType<typeof createResource>
) {
  const socket = getSocketInstance();

  // Socket payload has no avatar — reuse a resolved author from the feed, else fall back.
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
    const activity = normalizeActivity(key, doc, resolveAuthor);
    if (!activity) return;

    const current = (resource.data as Activity[] | undefined) ?? [];

    if (action === "add") {
      resource.data = [...current, activity];
    } else {
      resource.data = patchList(
        current,
        action as "update" | "delete",
        activity
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

function normalizeActivity(
  key: string,
  doc: Record<string, unknown>,
  resolveAuthor: (email: string | undefined, fallback: UserInfo) => UserInfo
): Activity | null {
  const timestamp = String(doc.creation);

  // comment-family rows carry the actor as `comment_email`/`comment_by`, else owner
  const commentEmail = (doc.comment_email as string) || (doc.owner as string);
  const author = resolveAuthor(commentEmail, {
    email: commentEmail,
    fullname: (doc.comment_by as string) || commentEmail,
  });

  switch (key) {
    case "comments":
      return {
        type: "comment",
        key: `comment:${doc.name}`,
        timestamp,
        author,
        data: { name: doc.name as string, content: doc.content as string },
      };

    case "like_logs":
      return {
        type: "log",
        key: `log:${doc.name}`,
        timestamp,
        author,
        data: {
          name: doc.name as string,
          subtype: "like",
          icon: "heart",
          text: `${author.fullname} liked`,
        },
      };

    case "assignment_logs": {
      const isCompleted = doc.comment_type === "Assignment Completed";
      return {
        type: "log",
        key: `log:${doc.name}`,
        timestamp,
        author,
        data: {
          name: doc.name as string,
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
      // private files live under /private/… — a stabler signal than the `fa-lock` icon
      return {
        type: "attachment_log",
        key: `attachment:${doc.name}`,
        timestamp,
        author,
        data: {
          name: doc.name as string,
          action: isRemoved ? "removed" : "added",
          fileName: stripHtml(content),
          isPrivate: fileUrl?.startsWith("/private/") ?? false,
          ...(fileUrl ? { fileUrl } : {}),
        },
      };
    }

    case "communications":
      return {
        type: "email",
        key: `email:${doc.name}`,
        timestamp: String(doc.communication_date || doc.creation),
        author: resolveAuthor(doc.sender as string, {
          email: doc.sender as string,
          fullname: (doc.sender_full_name || doc.sender) as string,
        }),
        data: {
          name: doc.name as string,
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

function patchList(
  list: Activity[],
  action: "update" | "delete",
  activity: Activity
): Activity[] {
  if (action === "delete") return list.filter((a) => a.key !== activity.key);
  return list.map((a) => (a.key === activity.key ? activity : a));
}

function dropDuplicateKeys(activities: Activity[]): Activity[] {
  const seen = new Set<string>();
  const out: Activity[] = [];
  for (const a of activities) {
    if (seen.has(a.key)) continue;
    seen.add(a.key);
    out.push(a);
  }
  return out;
}

function compareActivities(
  a: { timestamp?: string; key: string },
  b: { timestamp?: string; key: string }
): number {
  return (
    timeValue(a.timestamp) - timeValue(b.timestamp) ||
    a.key.localeCompare(b.key)
  );
}

function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, "").trim();
}

// Merge consecutive same-author versions into one summary; others pass through.
export function groupVersionActivities(activities: Activity[]): Activity[] {
  const out: Activity[] = [];
  let i = 0;
  while (i < activities.length) {
    const current = activities[i];
    if (current.type !== "version") {
      out.push(current);
      i++;
      continue;
    }
    let j = i + 1;
    while (
      j < activities.length &&
      activities[j].type === "version" &&
      activities[j].author?.fullname === current.author?.fullname
    ) {
      j++;
    }
    const summary = summarizeVersions(
      activities.slice(i, j) as VersionActivity[]
    );
    if (summary) out.push(summary);
    i = j;
  }
  return out;
}

// Collapse a run's changes into one summary row carrying a `group` of the individual
// changes; e.g. status Open→InProgress→Closed becomes status Open→Closed.
function summarizeVersions(
  versions: VersionActivity[]
): VersionActivity | null {
  const changes: VersionChange[] = []; // summary row; each a net change with full `history`
  const changeByField = new Map<string, VersionChange>(); // fieldname → its net change

  for (const row of versions) {
    const change = row.data;
    // doc-level rows have no fieldname — never collapse
    if (!change.fieldname) {
      changes.push({ ...change });
      continue;
    }
    const existing = changeByField.get(change.fieldname);
    if (!existing) {
      const next: VersionChange =
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
      changeByField.set(change.fieldname, next);
      changes.push(next);
    } else if (existing.type === "diff" && change.type === "diff") {
      existing.to = change.to; // advance net "to"; `from` stays the first row's
      existing.history!.push({
        from: change.from ?? "",
        to: change.to,
        timestamp: row.timestamp,
      });
    } else {
      // type changed mid-sequence (e.g. value edited then cleared) — take the latest
      const replacement: VersionChange = { ...change };
      changeByField.set(change.fieldname, replacement);
      changes[changes.indexOf(existing)] = replacement;
    }
  }

  // drop fields that churned back to their starting value (net no-op)
  const visible = changes.filter(
    (s) => !(s.type === "diff" && s.from === s.to)
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

// Frappe timestamps use a space separator; Date.parse needs 'T' for reliable parsing
function timeValue(ts?: string): number {
  if (!ts) return 0;
  const t = Date.parse(ts.includes(" ") ? ts.replace(" ", "T") : ts);
  return Number.isNaN(t) ? 0 : t;
}
