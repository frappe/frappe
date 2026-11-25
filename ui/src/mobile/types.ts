import type { Component } from "vue";
import type {
  NotificationLog,
  NotificationTab,
} from "../components/Notifications/types";

export interface SearchResult {
  label: string;
  description?: string;
  /** A `lucide-*` class name, or a component for an icon outside lucide. */
  icon?: string | Component;
}

export interface SearchProps<T extends SearchResult = SearchResult> {
  /** The rows to show. The host fetches them as `query` changes. */
  results: T[];
  loading?: boolean;
  placeholder?: string;
}

export interface ProfileGroupProps {
  label?: string;
}

export interface ProfileRowProps {
  label: string;
  /** Shown muted on the right, before the suffix: the current value of a setting. */
  value?: string;
  /** A `lucide-*` class name, or a component for an icon outside lucide. */
  icon?: string | Component;
  disabled?: boolean;
}

/** The same data props as NotificationPanel, so `useNotifications` feeds either. */
export interface NotificationsProps {
  notifications: NotificationLog[];
  unreadCount?: number;
  hasNextPage?: boolean;
  loading?: boolean;
  error?: unknown;
  /** Defaults to Unread and Read. */
  tabs?: NotificationTab[];
}
