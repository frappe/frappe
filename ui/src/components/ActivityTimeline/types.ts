import type { Component } from "vue";

export interface ActivityTimelineProps {
  /** The activities to render, already in display order. Produced by a source
   * composable (e.g. `useActivityTimeline`), keeping the renderer decoupled from where
   * activities come from. Accepts custom (consumer-defined) types alongside the
   * built-ins — render those via the `#item-{type}` slot. */
  activities: Array<Activity | CustomActivity>;
  /** Show the first-load spinner (only when there are no activities yet). */
  loading?: boolean;
  /** Error message to display instead of the feed. */
  error?: string | null;
}

export interface UserInfo {
  email?: string;
  fullname?: string;
  image?: string;
  name?: string;
}

export interface EmailAttachment {
  file_url: string;
  is_private?: 0 | 1;
  file_name?: string;
}

export interface BaseActivity<TType extends string, TData> {
  /** discriminant → picks the renderer/slot */
  type: TType;
  /** unique; v-for key + scroll target. Prefix by type (e.g. `sla_breach:1`). */
  key: string;
  /** Frappe / ISO datetime; sorted into the feed. Optional — pinned rows
   * (see `pin`) aren't sorted, so they don't need one. */
  timestamp?: string;
  /** gutter avatar + version grouping. Optional — authorless system events
   * may omit it. */
  author?: UserInfo;
  /** gutter icon: a lucide name (string) or a component (`<component :is>`).
   * When absent, the gutter falls to the per-type default. */
  icon?: string | Component;
  /** per-type payload */
  data: TData;
}

export type EmailActivity = BaseActivity<
  "email",
  {
    name: string;
    subject: string;
    sender: string;
    to: string;
    cc: string;
    bcc: string;
    content: string;
    deliveryStatus: string;
    attachments: EmailAttachment[];
  }
>;

export type CommentActivity = BaseActivity<
  "comment",
  {
    name: string;
    content: string;
  }
>;

export type AttachmentLogActivity = BaseActivity<
  "attachment_log",
  {
    name: string;
    action: "added" | "removed";
    fileName: string;
    fileUrl?: string;
    isPrivate: boolean;
  }
>;

export type LogActivity = BaseActivity<
  "log",
  {
    name: string;
    subtype:
      | "like"
      | "assigned"
      | "assignment_completed"
      | "workflow"
      | "info"
      | "view";
    /** lucide icon name (no prefix) */
    icon: string;
    /** final display string */
    text: string;
  }
>;

export type VersionActivity = BaseActivity<
  "version",
  {
    name: string;
    /** author-less phrase for this single change, e.g. "set Status to Resolved" */
    text: string;
    /** when present (length > 1), this is a grouped header; members are the
     *  consecutive same-author changes folded together */
    group?: VersionActivity[];
  }
>;

export type Activity =
  | EmailActivity
  | CommentActivity
  | AttachmentLogActivity
  | LogActivity
  | VersionActivity;

/** A consumer-defined activity the shared package doesn't know about — same
 * envelope as the built-ins, with an opaque `data` payload. The composable
 * returns only the doc's own activities; to add one of these, merge it into the
 * `activities` you pass to ActivityTimeline and render it via the
 * `#item-{type}` slot. The built-in `Activity` union stays closed so built-in
 * narrowing stays sharp. */
export type CustomActivity = Omit<BaseActivity<string, unknown>, "key"> & {
  /** Optional for custom rows — ActivityTimeline derives a fallback key (see
   * keyOf) when absent. Built-ins always carry one. Pass an explicit key when
   * the row can reorder, so v-for/scroll stay stable. */
  key?: string;
};

export interface EmailReplyPayload {
  content: string;
  to: string;
  cc?: string[];
  bcc?: string[];
}

/** A built-in item action surfaced through its `#actions` slot. The item renders
 * these as its default buttons; a consumer who overrides `#actions` gets the same
 * list as a slot prop, so it can render the defaults, add its own, or both. */
export interface TimelineAction {
  /** stable id — `"reply"` | `"reply-all"` | `"edit"` | `"delete"` | … */
  key: string;
  /** tooltip / aria label (already translated by the item) */
  label: string;
  /** lucide/feather name (string) or an icon component */
  icon: string | Component;
  /** Button theme — omit for default; `"red"` for destructive actions */
  theme?: string;
  /** run the built-in behavior (emits `reply` / `edit` / `delete`) */
  onClick: () => void;
}
