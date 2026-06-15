import { createResource, request } from "frappe-ui";
import { computed } from "vue";
import type {
  Activity,
  CommentActivity,
  Docinfo,
  EmailActivity,
  EmailAttachment,
} from "./types";

// get_docinfo writes to frappe.response["docinfo"] instead of returning, so the
// payload lands beside "message" in the HTTP response — a custom fetcher is
// needed because frappe-ui's default fetchers only surface "message".
function docinfoFetcher(options: Record<string, any>) {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json; charset=utf-8",
    "X-Frappe-Site-Name": window.location.hostname,
  };
  const csrfToken = (window as any).csrf_token;
  if (csrfToken && csrfToken !== "{{ csrf_token }}") {
    headers["X-Frappe-CSRF-Token"] = csrfToken;
  }
  return request({
    url: "/api/method/frappe.desk.form.load.get_docinfo",
    method: "POST",
    params: options.params,
    signal: options.signal,
    headers,
    transformResponse: async (response: Response) => {
      if (!response.ok) {
        let messages: string[] = [];
        try {
          const error = await response.json();
          messages = (
            error._server_messages ? JSON.parse(error._server_messages) : []
          )
            .map((m: string) => {
              try {
                return JSON.parse(m).message;
              } catch {
                return m;
              }
            })
            .filter(Boolean);
          if (!messages.length && error._error_message)
            messages = [error._error_message];
        } catch {
          // non-JSON error body
        }
        const e = new Error(
          messages.join("\n") || response.statusText
        ) as Error & {
          response: Response;
          messages: string[];
        };
        e.response = response;
        e.messages = messages;
        throw e;
      }
      const data = await response.json();
      return data.docinfo as Docinfo;
    },
  });
}

function parseAttachments(
  attachments?: string | EmailAttachment[]
): EmailAttachment[] {
  if (!attachments) return [];
  const parsed =
    typeof attachments === "string" ? JSON.parse(attachments) : attachments;
  return (parsed || []).map((a: EmailAttachment) => ({
    ...a,
    file_name: a.file_name || a.file_url?.split("/").pop(),
  }));
}

// docinfo → every activity on the doc, merged and chronologically sorted
function parseActivities(docinfo: Docinfo): Activity[] {
  const { user_info = {} } = docinfo;

  const emails: EmailActivity[] = [
    ...(docinfo.communications || []),
    ...(docinfo.automated_messages || []),
  ].map((c) => ({
    type: "email",
    key: `email:${c.name}`,
    name: c.name,
    timestamp: c.communication_date || c.creation,
    subject: c.subject,
    sender: c.sender,
    senderFullName: c.sender_full_name || user_info[c.sender]?.fullname || c.sender,
    senderImage: user_info[c.sender]?.image,
    to: c.recipients,
    cc: c.cc,
    bcc: c.bcc,
    content: c.content,
    deliveryStatus: c.delivery_status,
    attachments: parseAttachments(c.attachments),
  }));

  const comments: CommentActivity[] = (docinfo.comments || []).map((c) => ({
    type: "comment",
    key: `comment:${c.name}`,
    name: c.name,
    timestamp: c.creation,
    content: c.content,
    author: user_info[c.owner] || { email: c.owner, fullname: c.owner },
  }));

  // frappe datetimes (YYYY-MM-DD HH:mm:ss.ffffff) sort correctly as strings
  return [...emails, ...comments].sort(
    (a, b) =>
      a.timestamp.localeCompare(b.timestamp) || a.key.localeCompare(b.key)
  );
}

// One resource per doctype:docname, shared by all useDocInfo() callers and
// fetched once per session — remounts reuse the cached data without a new
// request. Freshness is the caller's concern via reload() (or realtime, later).
const docinfoResources = new Map<string, ReturnType<typeof createResource>>();

function getResource(doctype: string, docname: string) {
  const key = `${doctype}:${docname}`;
  let resource = docinfoResources.get(key);
  if (!resource) {
    resource = createResource({
      url: "frappe.desk.form.load.get_docinfo",
      params: { doctype, name: docname },
      resourceFetcher: docinfoFetcher,
      transform: parseActivities,
      cache: key, // ensure separate cache entries for different docs
      auto: true,
    });
    docinfoResources.set(key, resource);
  }
  return resource;
}

/**
 * Fetches a document's docinfo and exposes everything on it as one
 * chronologically sorted activities list. Fetched once per doctype/docname
 * per session; revisiting a doc reuses the cached data without a new
 * request. Call reload() to refresh.
 *
 * Args are plain strings, bound once — to show a different doc, remount the
 * consuming component (e.g. with a :key).
 *
 *   const { activities, loading, error, reload } = useDocInfo("HD Ticket", "37422")
 */
export function useDocInfo(doctype: string, docname: string) {
  const resource = getResource(doctype, docname);

  return {
    activities: computed<Activity[]>(() => resource.data || []),
    loading: computed<boolean>(() => resource.loading),
    error: computed(() => resource.error),
    reload: () => resource.reload(),
  };
}
