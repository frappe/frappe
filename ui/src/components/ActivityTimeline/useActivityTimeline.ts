import { call, createResource } from "frappe-ui";
import {
  computed,
  onMounted,
  onUnmounted,
  reactive,
  ref,
  watch,
  type Ref,
} from "vue";
import { getSocketInstance } from "../../socket";
import type { Activity, UserInfo, VersionActivity } from "./types";

// shape returned by get_activity_timeline / get_more_email_activities
interface TimelineData {
  activities: Activity[];
  has_more_emails: boolean;
}

const resources = new Map<string, ReturnType<typeof createResource>>();

export function useActivityTimeline(doctype: string, docname: string) {
  const key = `${doctype}:${docname}`;
  let resource = resources.get(key);
  if (!resource) {
    resource = createResource({
      url: "frappe.desk.form.activity.get_activity_timeline",
      params: { doctype, name: docname },
      cache: `activities:${key}`,
      auto: true,
    });
    resources.set(key, resource);
  }

  // The email stream is paged. The first page lives in `resource.data`; further
  // pages accumulate in `extraEmails` and merge in the `activities` computed.
  const extraEmails = ref<Activity[]>([]);
  const hasNextPage = ref(false);
  const isFetchingNextPage = ref(false);

  // Email count of the first page (the oldest run), captured once. A realtime
  // email-add lands in `resource.data` but is NOT part of the oldest run, so the
  // next page's offset is `firstPageEmails + extraEmails.length` — never derived
  // from the live (mutating) list, which would skip a row after a live add.
  let firstPageEmails = 0;
  let firstPageSeen = false;

  watch(
    () => resource.data as TimelineData | undefined,
    (data) => {
      if (!data) return;
      if (!firstPageSeen) {
        firstPageEmails = countEmails(data.activities);
        firstPageSeen = true;
      }
      // server flag owns hasNextPage until the user starts paging
      if (!extraEmails.value.length) {
        hasNextPage.value = data.has_more_emails ?? false;
      }
    },
    { immediate: true }
  );

  handleLiveUpdates(doctype, docname, resource, extraEmails);

  async function fetchNextPage() {
    if (isFetchingNextPage.value || !hasNextPage.value) return;
    isFetchingNextPage.value = true;
    try {
      const start = firstPageEmails + extraEmails.value.length;
      const res = (await call(
        "frappe.desk.form.activity.get_more_email_activities",
        { doctype, name: docname, start }
      )) as TimelineData;
      extraEmails.value = [...extraEmails.value, ...(res.activities ?? [])];
      hasNextPage.value = res.has_more_emails ?? false;
    } finally {
      isFetchingNextPage.value = false;
    }
  }

  return {
    activities: computed<Activity[]>(() => {
      const base =
        (resource.data as TimelineData | undefined)?.activities ?? [];
      const merged = dedupeByKey([...base, ...extraEmails.value]);
      merged.sort(compareActivities);
      return groupConsecutiveVersions(merged);
    }),
    loading: computed<boolean>(() => resource.loading),
    error: computed(() => resource.error || null),
    pagination: reactive({
      hasNextPage,
      isFetchingNextPage,
      fetchNextPage,
    }),
    reload: () => resource.reload(),
  };
}

function dedupeByKey(activities: Activity[]): Activity[] {
  const seen = new Set<string>();
  const out: Activity[] = [];
  for (const a of activities) {
    if (seen.has(a.key)) continue;
    seen.add(a.key);
    out.push(a);
  }
  return out;
}

function countEmails(activities: Activity[]): number {
  return activities.filter((a) => a.type === "email").length;
}

function patchList(
  list: Activity[],
  action: "update" | "delete",
  activity: Activity
): Activity[] {
  if (action === "delete") return list.filter((a) => a.key !== activity.key);
  return list.map((a) => (a.key === activity.key ? activity : a));
}

function handleLiveUpdates(
  doctype: string,
  docname: string,
  resource: ReturnType<typeof createResource>,
  extraEmails: Ref<Activity[]>
) {
  const socket = getSocketInstance();

  // The socket payload only carries a userid (+ best-effort name), no avatar.
  // Reuse the fully-resolved author of anyone already in the feed; first-time
  // actors fall back to the payload and self-heal on the next reload.
  const resolveAuthor = (email: string | undefined, fallback: UserInfo) => {
    if (!email) return fallback;
    const known = [
      ...((resource.data as TimelineData | undefined)?.activities ?? []),
      ...extraEmails.value,
    ].find((a) => a.author?.email === email)?.author;
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

    const data = (resource.data as TimelineData | undefined) ?? {
      activities: [],
      has_more_emails: false,
    };
    const current = data.activities ?? [];

    if (action === "add") {
      // new rows go to the first-page list and sort into place via the computed
      resource.data = { ...data, activities: [...current, activity] };
    } else {
      // update/delete may target a row in either list (e.g. a paged-in email)
      resource.data = { ...data, activities: patchList(current, action, activity) };
      extraEmails.value = patchList(extraEmails.value, action, activity);
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

  // comment-family rows (comments, likes, assignments, attachments) carry the
  // actor as `comment_email` (+ `comment_by` display name) or fall back to owner
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
      return {
        type: "attachment_log",
        key: `attachment:${doc.name}`,
        timestamp,
        author,
        data: {
          name: doc.name as string,
          action: isRemoved ? "removed" : "added",
          fileName: stripHtml(content),
          fileUrl: !isRemoved && href ? href[1] : undefined,
          isPrivate: content.includes("fa-lock"),
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

function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, "").trim();
}

export function groupConsecutiveVersions(activities: Activity[]): Activity[] {
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
    if (j - i === 1) {
      out.push(current);
    } else {
      const run = activities.slice(i, j) as VersionActivity[];
      const cur = current as VersionActivity;
      out.push({ ...cur, data: { ...cur.data, group: run } });
    }
    i = j;
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

// Frappe timestamps use a space separator; Date.parse needs 'T' for reliable parsing
function timeValue(ts?: string): number {
  if (!ts) return 0;
  const t = Date.parse(ts.includes(" ") ? ts.replace(" ", "T") : ts);
  return Number.isNaN(t) ? 0 : t;
}
