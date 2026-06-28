import { createResource } from "frappe-ui";
import { computed, onMounted, onUnmounted } from "vue";
import { getSocketInstance } from "../../socket";
import type {
  Activity,
  UserInfo,
  VersionActivity,
  VersionChange,
} from "./types";

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

  handleLiveUpdates(doctype, docname, resource);

  return {
    activities: computed<Activity[]>(() => {
      const base = (resource.data as Activity[] | undefined) ?? [];
      const merged = dropDuplicateKeys(base);
      merged.sort(compareActivities);
      return groupVersionActivities(merged);
    }),
    loading: computed<boolean>(() => resource.loading),
    error: computed(() => resource.error || null),
    reload: () => resource.reload(),
  };
}

function handleLiveUpdates(
  doctype: string,
  docname: string,
  resource: ReturnType<typeof createResource>
) {
  const socket = getSocketInstance();

  // The socket payload only carries a userid (+ best-effort name), no avatar.
  // Reuse the fully-resolved author of anyone already in the feed; first-time
  // actors fall back to the payload and self-heal on the next reload.
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
      // new rows append and sort into place via the computed
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
      const fileUrl = !isRemoved && href ? href[1] : undefined;
      // private files are served from /private/files/… — a stable signal,
      // unlike sniffing the `fa-lock` icon class out of the comment HTML
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

// Merge consecutive same-author versions into one summary; other activities pass through.
// Groups changes by same user into one
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

// Group similar version changes into one summary row, with a `group` of the individual changes.
/* example: 
  `status Open -> Closed`, status Open -> In Progress, status In Progress -> Closed` becomes `status Open -> Closed` with a `group` of the three changes. 
*/
function summarizeVersions(
  versions: VersionActivity[]
): VersionActivity | null {
  const changes: VersionChange[] = []; // for the summary row; each is a net change (first.from → last.to) with a `history` of all similar changes in the run
  const changeByField = new Map<string, VersionChange>(); // keyed by `fieldname` to find the net change for each field

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
          ? { ...change, history: [{ from: change.from ?? "", to: change.to }] }
          : { ...change };
      changeByField.set(change.fieldname, next);
      changes.push(next);
    } else if (existing.type === "diff" && change.type === "diff") {
      existing.to = change.to; // advance net "to"; `from` stays the first row's
      existing.history!.push({ from: change.from ?? "", to: change.to });
    } else {
      // type changed mid-sequence (e.g. value edited then cleared) — take the latest
      const replacement: VersionChange = { ...change };
      changeByField.set(change.fieldname, replacement);
      changes[changes.indexOf(existing)] = replacement;
    }
  }

  // drop fields that churned back to their starting value (net no-op; `from` is the
  // first row's, so this never matches a set-from-blank, which has no `from`)
  const visible = changes.filter(
    (s) => !(s.type === "diff" && s.from === s.to)
  );
  if (visible.length === 0) return null;

  // key off the first row (stable identity) so Vue reuses the item on re-derive
  // instead of remounting and resetting its expanded state; timestamp from the last
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
