import type { Component } from "vue";
import type { UploadedFile } from "frappe-ui/editor";

export interface ActivityTimelineProps {
  /** Rows in display order. Custom types render via the `#item-{type}` slot. */
  activities: Array<Activity | CustomActivity>;
  /** First-load spinner; only shown while there are no activities yet. */
  loading?: boolean;
  /** Enables Load More; same object useActivityTimeline returns. */
  paginate?: Pagination;
}

export interface Pagination {
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => void;
  /**
   * Rows the next page extends, which is where an inline `load_more` row sits.
   * Defaults to email rows.
   */
  isPagedRow?: (activity: Activity | CustomActivity) => boolean;
  /** Load More affordance; omit for a default "Load more" button at the top. */
  loadMore?: {
    /** Placement. "inline" injects a `load_more` row above the oldest paged row. */
    position?: "top" | "bottom" | "inline";
    /** Button copy; default "Load more" / "lucide-refresh-cw". */
    label?: string;
    /** lucide-* string, FeatherIcon name, or a component — same as `Button`'s icon. */
    icon?: string | Component;
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
  /** lucide name or component; per-type default when absent */
  icon?: string | Component;
  data: TData;
}

export type EmailActivity = BaseActivity<
  "email",
  {
    name: string;
    subject?: string;
    sender: string;
    to?: string;
    cc?: string;
    bcc?: string;
    content: string;
    deliveryStatus?: string;
    attachments?: EmailAttachment[];
  }
>;

export type CommentActivity = BaseActivity<
  "comment",
  {
    name: string;
    content: string;
    attachments?: EmailAttachment[];
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
      | "view"
      | "created"
      | "edited"
      | "shared"
      | "milestone";
    text: string;
    /** assignee on assignment logs; bolded alongside the actor (backend-supplied) */
    assignee?: string;
    /** set when consecutive assignment logs fold into one row; all bolded */
    assignees?: string[];
  }
>;

interface VersionChangeBase {
  name: string;
  /** field changes carry it (enables same-field collapse); doc-level rows don't */
  fieldname?: string | null;
  /** when this net change last happened; shown per-row inside a folded group */
  timestamp?: string;
}

/** One field change: old → new value (empty `from` ⇒ set-from-blank). */
export interface FieldChange {
  from: string;
  to: string;
  timestamp: string;
}

/** A shown field change; the frontend lays out the values. */
export interface DiffChange extends VersionChangeBase {
  type: "diff";
  /** translated lead phrase, e.g. "changed Status" / "set Priority to" */
  prefix: string;
  /** old value (frontend-truncated); absent ⇒ set-from-blank, no arrow */
  from?: string;
  to: string;
  /** every field change across merged saves; absent/length-1 ⇒ no chevron */
  history?: FieldChange[];
}

/** A value-less change described in words (long-text edits, clears, submit/cancel). */
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
  /** Omit for static lists; reorderable rows need a key for stable v-for/scroll. */
  key?: string;
};

// —— Per-activity-row components (rendered by ActivityTimeline via its type slots) ——

export interface EmailItemProps {
  email: EmailActivity;
}
export interface EmailItemSlots {
  /** Replaces the row header (sender, subject, timestamp). */
  header?: (props: { email: EmailActivity }) => any;
  /** Trailing actions in the header. */
  actions?: () => any;
  /** Replaces the row footer. */
  footer?: (props: { email: EmailActivity }) => any;
}

export interface CommentItemProps {
  comment: CommentActivity;
  editable?: boolean;
  /** classes on the editor content; default "prose-sm max-w-none" */
  editorClass?: string;
  /** image upload handler passed through to the editor while editing */
  uploadFunction?: (file: File) => Promise<UploadedFile>;
}
export interface CommentItemSlots {
  /** Replaces the row header (author, timestamp). */
  header?: (props: { comment: CommentActivity }) => any;
  /** Trailing actions in the header. */
  actions?: () => any;
  /** Replaces the row footer. */
  footer?: (props: { comment: CommentActivity }) => any;
}

export interface LogItemProps {
  activity: LogActivity | AttachmentLogActivity;
}

export interface VersionItemProps {
  activity: VersionActivity;
}
