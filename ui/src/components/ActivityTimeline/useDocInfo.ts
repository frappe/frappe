import { createResource, request } from "frappe-ui";
import { computed } from "vue";
import type {
  Activity,
  AttachmentLogActivity,
  AuditActivity,
  CommentActivity,
  Docinfo,
  DocinfoComment,
  EmailActivity,
  EmailAttachment,
  UserInfo,
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

// Strip tags to readable text (desk audit content may contain <b> etc.)
function plaintext(html: string): string {
  return new DOMParser().parseFromString(html || "", "text/html").body
    .textContent?.trim() || "";
}

// Comment-based attachment log → structured fields (discard the desk HTML).
// "Attachment": content is <a href='{url}'>{name}</a> (+ optional fa-lock <i>).
// "Attachment Removed": content is the bare filename, no link.
function parseAttachmentLog(
  c: DocinfoComment,
  author: UserInfo
): AttachmentLogActivity {
  const action = c.comment_type === "Attachment Removed" ? "removed" : "added";
  const anchor = new DOMParser()
    .parseFromString(c.content || "", "text/html")
    .querySelector("a");
  const fileName = (anchor?.textContent ?? plaintext(c.content)).trim();
  const fileUrl =
    action === "added" ? anchor?.getAttribute("href") || undefined : undefined;
  return {
    type: "attachment_log",
    key: `attachment:${c.name}`,
    name: c.name,
    timestamp: c.creation,
    action,
    fileName,
    fileUrl,
    isPrivate: /fa-lock/.test(c.content || ""),
    author,
  };
}

// docinfo → every activity on the doc, merged and chronologically sorted
function parseActivities(docinfo: Docinfo): Activity[] {
  const { user_info = {} } = docinfo;

  const authorOf = (owner: string): UserInfo =>
    user_info[owner] || { email: owner, fullname: owner };

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
    author: authorOf(c.owner),
  }));

  const attachmentLogs: AttachmentLogActivity[] = (
    docinfo.attachment_logs || []
  ).map((c) => parseAttachmentLog(c, authorOf(c.owner)));

  // Comment-based audit logs → one-line AuditActivity entries. Build the display
  // text from structured fields/plaintext; never reuse the desk-link HTML.
  const audits: AuditActivity[] = [];

  const pushAudit = (
    c: DocinfoComment,
    subtype: AuditActivity["subtype"],
    icon: string,
    text: string
  ) => {
    audits.push({
      type: "audit",
      key: `audit:${c.name}`,
      name: c.name,
      timestamp: c.creation,
      subtype,
      icon,
      text,
      author: authorOf(c.owner),
    });
  };

  for (const c of docinfo.like_logs || []) {
    pushAudit(c, "like", "heart", `${authorOf(c.owner).fullname} liked`);
  }
  for (const c of docinfo.assignment_logs || []) {
    if (c.comment_type === "Assignment Completed") {
      pushAudit(c, "assignment_completed", "circle-check", plaintext(c.content));
    } else {
      pushAudit(c, "assigned", "user-plus", plaintext(c.content));
    }
  }
  for (const c of docinfo.workflow_logs || []) {
    pushAudit(
      c,
      "workflow",
      "git-branch",
      `${authorOf(c.owner).fullname} ${plaintext(c.content)}`
    );
  }
  for (const c of docinfo.info_logs || []) {
    pushAudit(
      c,
      "info",
      "info",
      `${authorOf(c.owner).fullname} ${plaintext(c.content)}`
    );
  }

  // frappe datetimes (YYYY-MM-DD HH:mm:ss.ffffff) sort correctly as strings
  return [...emails, ...comments, ...attachmentLogs, ...audits].sort(
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
