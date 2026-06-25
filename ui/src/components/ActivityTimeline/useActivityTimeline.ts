import { createResource } from "frappe-ui";
import { computed, onMounted, onUnmounted } from "vue";
import { getSocketInstance } from "../../socket";
import type { Activity, VersionActivity } from "./types";

const resources = new Map<string, ReturnType<typeof createResource>>();

export function useActivityTimeline(
  doctype: string,
  docname: string,
  order: "asc" | "desc" = "desc"
) {
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
      const list = [...((resource.data as Activity[]) || [])];
      list.sort(compareActivities);
      const grouped = groupConsecutiveVersions(list);
      return order === "desc" ? grouped.reverse() : grouped;
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

  const onUpdate = (payload: unknown) => {
    const { doc, key, action } = payload as {
      doc: Record<string, unknown>;
      key: string;
      action: "add" | "update" | "delete";
    };
    const activity = normalizeActivity(key, doc);
    if (!activity) return;

    const current = (resource.data as Activity[]) || [];
    if (action === "add") {
      resource.data = [...current, activity];
    } else if (action === "update") {
      resource.data = current.map((a) => (a.key === activity.key ? activity : a));
    } else if (action === "delete") {
      resource.data = current.filter((a) => a.key !== activity.key);
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
  doc: Record<string, unknown>
): Activity | null {
  const timestamp = String(doc.creation);
  const author = { email: doc.owner as string, fullname: doc.owner as string };

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
          text: `${doc.owner} liked`,
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
        author: {
          email: doc.sender as string,
          fullname: (doc.sender_full_name || doc.sender) as string,
        },
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
