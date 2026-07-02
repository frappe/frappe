import { createResource } from "frappe-ui";
import { computed, onMounted, onUnmounted, reactive, ref, type Ref } from "vue";
import { getSocketInstance } from "../../socket";
import type {
  Activity,
  CustomActivity,
  Pagination,
  UserInfo,
} from "./types";
import {
  compareActivities,
  dropDuplicateKeys,
  groupActivities,
} from "./grouping";
import { getAssignee, stripHtml } from "./utils";

// One resource per doctype:docname for the session, so reopening a doc is instant.
const resources = new Map<string, ReturnType<typeof createResource>>();

// "older emails remain" flag, kept outside the resource so it survives cached remounts.
const hasMoreEmailsByKey = new Map<string, Ref<boolean>>();

export function useActivityTimeline(doctype: string, docname: string) {
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
      // transform sets resource.data; onSuccess still sees the raw response, so
      // has_more_emails is read there (not from transform's output). On reload
      // (e.g. a doc_update), re-append the older email pages the user has already loaded.
      transform: (res: { activities: Activity[] }) => {
        const oldActivities = (resource.data as Activity[] | undefined) ?? [];

        const newActivities = res.activities;
        const newActivityKeys = new Set(newActivities.map((a) => a.key));

        const paginatedOlderEmails = oldActivities.filter(
          (a) => a.type === "email" && !newActivityKeys.has(a.key)
        );
        return [...newActivities, ...paginatedOlderEmails];
      },
      onSuccess: (res: { has_more_emails?: boolean }) => {
        hasMoreEmails!.value = !!res.has_more_emails;
      },
    });
    resources.set(cacheKey, resource);
  }

  subscribeToLiveUpdates(doctype, docname, resource);

  const activities = computed<Array<Activity | CustomActivity>>(() => {
    const fetched = (resource.data as Activity[] | undefined) ?? [];
    const uniqueActivities = dropDuplicateKeys(fetched);
    uniqueActivities.sort(compareActivities);
    return groupActivities(uniqueActivities);
  });

  return {
    activities,
    loading: computed<boolean>(() => resource.loading),
    reload: () => resource.reload(),
    paginate: createEmailPagination(doctype, docname, resource, hasMoreEmails),
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
    // in-feed row above the oldest email; email-specific copy lives here, not in the component
    loadMore: {
      position: "inline" as const,
      label: "Show previous conversations",
      icon: "lucide-chevrons-up",
    },
  });
}

function subscribeToLiveUpdates(
  doctype: string,
  docname: string,
  resource: ReturnType<typeof createResource>
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
