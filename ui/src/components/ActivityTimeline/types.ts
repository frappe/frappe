import type { Component } from "vue";

export interface ActivityTimelineProps {
  /** Custom types render via the `#item-{type}` slot. */
  activities: Array<Activity | CustomActivity>;
  /** Only shown when there are no activities yet. */
  loading?: boolean;
  error?: string | null;
  /** Infinite-scroll controls. Omit to disable auto-loading (static feed). */
  infiniteScroll?: InfiniteScrollControls;
}

/** Controls for scroll-driven pagination — shape matches TanStack useInfiniteQuery. */
export interface InfiniteScrollControls {
  /** Whether another page can be fetched. */
  hasNextPage?: boolean;
  /** A page fetch is in flight — drives the bottom spinner and gates re-entry. */
  isFetchingNextPage?: boolean;
  /** Fetch the next page (appends to the source). */
  fetchNextPage?: () => void | Promise<void>;
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
  }
>;

export type VersionActivity = BaseActivity<
  "version",
  {
    name: string;
    /** e.g. "set Status to Resolved" */
    text: string;
    /** present when consecutive same-author changes are folded together */
    group?: VersionActivity[];
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
  /** Omit only for static lists — ActivityTimeline derives a fallback, but
   * reorderable rows need an explicit key for stable v-for/scroll. */
  key?: string;
};
