import type { createResource } from "frappe-ui";
import { getSocketInstance, subscribeToDoc } from "../../socket";
import type { Activity, UserInfo } from "./types";
import { getAssignee, stripHtml } from "./utils";

export type Unsubscribe = () => void;
export type Subscribe = () => Unsubscribe;

// realtime is off, so there is nothing to join and nothing to leave
const noLiveUpdates: Subscribe = () => () => {};

/** Returns subscribe(): the first caller wires the socket, the last unwires it. */
export function createLiveUpdates(
  doctype: string,
  docname: string,
  resource: ReturnType<typeof createResource>,
  visibleTypes: string[] | undefined,
  refresh: () => Promise<void>
): Subscribe {
  const socket = getSocketInstance();
  if (!socket) return noLiveUpdates;

  // The payload has no avatar, so reuse an author already resolved in the feed.
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

  // A reconnect misses whatever was sent while down, so the feed must catch up.
  // `connect` fires on the first connect too, hence the flag.
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
      // mirror the backend so the assignee bolds on live rows too
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
          // private files live under /private/, stabler than the fa-lock icon
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
