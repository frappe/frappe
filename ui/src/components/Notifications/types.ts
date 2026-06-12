import type { Component } from "vue";

export interface NotificationLog {
  name: string;
  /** canonical headline shown in the panel */
  title?: string;
  /** canonical body shown under the title */
  description?: string;
  /** email representation of the title (read when the notification is emailed) */
  subject?: string;
  type?: string;
  /** app that produced this notification — used to scope the panel to a single app */
  app?: string;
  read: number | boolean;
  from_user?: string;
  /** sender's photo, when resolved — used for the default avatar */
  from_user_image?: string;
  document_type?: string;
  document_name?: string;
  link?: string;
  creation: string;
  // app-specific Custom Fields flow through untyped
  [key: string]: unknown;
}

/** Notification Type is purely categorical — used for tabs/filters, not presentation. */
export interface NotificationType {
  name: string;
  type_name?: string;
  enabled?: number | boolean;
}

/**
 * Leading visual for a row. A lucide icon name (rendered via frappe-ui) or a Component.
 * When omitted, the row renders the sender's Avatar by default.
 */
export type NotificationIcon = string | Component;

export interface NotificationTab {
  label: string;
  /** server-side filters applied to the Notification Log list query */
  filters?: Record<string, unknown>;
  /** client-side predicate applied to the already-fetched rows */
  filterFn?: (n: NotificationLog) => boolean;
  /** badge next to the tab label */
  count?: "unread" | ((items: NotificationLog[]) => number);
}

export interface NotificationPanelProps {
  /** scope the feed to a single app — only notifications about that app's documents are shown */
  appName?: string;
  /**
   * recipient to scope the feed to (`for_user`). Defaults to the logged-in user. Pass it to
   * avoid a lookup round-trip, or to view a specific user's feed (e.g. a demo). Without it, an
   * Administrator session would see every user's notifications.
   */
  currentUser?: string;
  /** Notification Log fields to fetch; defaults include the generic set. Append custom fields here. */
  fields?: string[];
  tabs?: NotificationTab[];
  showMarkAllRead?: boolean;
  showClose?: boolean;
  pageLength?: number;
  title?: string;
  /** host routing hook; called (in addition to @item-click) when a row is clicked */
  onItemClick?: (n: NotificationLog) => void;
  /**
   * Resolve the leading visual per row: return a lucide icon name (string) or a Component.
   * Return undefined to fall back to the sender's avatar (the default for most rows).
   */
  icon?: (n: NotificationLog) => NotificationIcon | undefined;
  /** a frappe-ui / socket.io socket; if provided, the panel live-reloads on the `notification` event */
  socket?: {
    on: (event: string, cb: (...args: unknown[]) => void) => void;
    off?: (event: string, cb: (...args: unknown[]) => void) => void;
  };
}
