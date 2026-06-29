import type { Component } from "vue";

export interface ActivityTimelineProps {
  /** Custom types render via the `#item-{type}` slot. */
  activities: Array<Activity | CustomActivity>;
  /** Only shown when there are no activities yet. */
  loading?: boolean;
  error?: string | null;
  /** When present, enables scroll-up email pagination. Same object returned by useActivityTimeline. */
  paginate?: {
    hasNextPage: boolean;
    isFetchingNextPage: boolean;
    fetchNextPage: () => void;
  };
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
  /** v-for key + scroll target; prefix by type (e.g. `sla_breach:1`) */
  key: string;
  timestamp?: string;
  author?: UserInfo;
  /** lucide name or component; falls back to the per-type default when absent */
  icon?: string | Component;
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
    /** lucide name, no prefix */
    icon: string;
    text: string;
    /** present when consecutive same-author log rows are folded together */
    group?: LogActivity[];
  }
>;

interface VersionChangeBase {
  name: string;
  /** field changes carry it (enables same-field collapse); doc-level rows don't */
  fieldname?: string | null;
}

/** One field change: old → new value (empty `from` ⇒ set-from-blank). */
export interface FieldChange {
  from: string;
  to: string;
  timestamp: string;
}

/** A field value changed and we can show it — the frontend lays out the values. */
export interface DiffChange extends VersionChangeBase {
  type: "diff";
  /** translated lead phrase, e.g. "changed Status" / "set Priority to" */
  prefix: string;
  /** old value (truncated by the frontend); absent ⇒ set-from-blank, no arrow */
  from?: string;
  to: string;
  /** every field change across merged saves; absent/length-1 ⇒ no chevron */
  history?: FieldChange[];
}

/** A value-less change described in words (long-text edits, clears, submit/cancel/rows). */
export interface PhraseChange extends VersionChangeBase {
  type: "phrase";
  /** full translated line, e.g. "updated Description" / "submitted this document" */
  text: string;
}

/** One change in a version; `type` picks the layout: diff (from→to) or phrase (value-less). */
export type VersionChange = DiffChange | PhraseChange;

export type VersionActivity = BaseActivity<
  "version",
  VersionChange & {
    /** set when a sequence folds into >1 change */
    group?: VersionChange[];
  }
>;

export type Activity =
  | EmailActivity
  | CommentActivity
  | AttachmentLogActivity
  | LogActivity
  | VersionActivity;

/** Consumer-defined activity; render via the `#item-{type}` slot. */
export type CustomActivity = Omit<BaseActivity<string, unknown>, "key"> & {
  /** Omit only for static lists; reorderable rows need an explicit key for stable v-for/scroll. */
  key?: string;
};
