export interface NotificationLog {
  name: string;
  /** canonical headline shown in the panel — HTML, sanitized by the backend at write time */
  title?: string;
  /** canonical body shown under the title — HTML, sanitized by the backend at write time */
  description?: string;
  /** email representation of the title; used as the title fallback */
  subject?: string;
  /** opaque category tag — used only for filtering, never for presentation */
  type?: string;
  /** app that produced this notification — used to scope the panel to a single app */
  app?: string;
  read: number | boolean;
  from_user?: string;
  /**
   * sender's photo for the default avatar. Resolved client-side today (see useNotifications);
   * a candidate to become a server virtual field so the feed query carries it directly.
   */
  from_user_image?: string;
  document_type?: string;
  document_name?: string;
  link?: string;
  creation: string;
  // app-specific Custom Fields flow through untyped (the feed is fetched with `["*"]`)
  [key: string]: unknown;
}

/** Minimal socket.io-compatible emitter. Supplied by the host to `useNotifications`. */
export interface NotificationSocket {
  on: (event: string, cb: (...args: unknown[]) => void) => void;
  off?: (event: string, cb: (...args: unknown[]) => void) => void;
}

/**
 * A tab is a label + a filter. The filter is overloaded by type:
 *   - object   → server-side filter merged into the feed query (affects counts + pagination)
 *   - function → client-side predicate applied to already-fetched rows
 * `value` is the stable key (used for the dynamic `#tab-<value>` slot); defaults to the label.
 */
export interface NotificationTab {
  label: string;
  value?: string;
  filter?: Record<string, unknown> | ((n: NotificationLog) => boolean);
  /** badge next to the label: the server unread count, or a count derived from fetched rows */
  count?: "unread" | ((items: NotificationLog[]) => number);
}

/** Options for the data plugin. The host owns this; the panel never sees socket/scope. */
export interface UseNotificationsOptions {
  pageLength?: number;
  /** scope the feed to a single app (matched on the denormalized `app` column) */
  appName?: string;
  /**
   * recipient scope (`for_user`); defaults to the logged-in user, resolved lazily. Pass it to
   * skip a lookup, or to view a specific user's feed. Without it an Administrator session would
   * see every user's notifications (Notification Log permits an admin to read everyone's).
   */
  currentUser?: string;
  /** initial server-side filters; tabs layer on top via `setFilters` */
  filters?: Record<string, unknown>;
  socket?: NotificationSocket;
}

/**
 * The injected controller returned by `useNotifications()`. It is a `reactive` proxy, so its
 * members read as plain (live) values — spread it onto the panel with `v-bind="controller"`.
 * Read members directly (e.g. `controller.notifications`); destructuring would drop reactivity.
 * State is read-only from the consumer's side — mutate only through the verbs.
 */
export interface NotificationStore {
  notifications: NotificationLog[];
  unreadCount: number;
  hasNextPage: boolean;
  /** true only on a cold load with nothing cached — lets the panel hold off the empty state */
  loading: boolean;
  /** last fetch error, surfaced to the panel's `#error` slot */
  error: unknown;
  markAsRead: (name: string) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  /** clear the bell's unseen indicator — the host calls this when it opens the panel */
  markSeen: () => void;
  reload: () => void;
  loadMore: () => void;
  /** set arbitrary server filters; app + recipient scope are always preserved */
  setFilters: (filters: Record<string, unknown>) => void;
  /** apply a tab's object filter to the feed (function filters are client-side, in the panel) */
  filterByTab: (tab?: NotificationTab) => void;
}

/**
 * Panel props are *data* only — spread the controller's data members via `v-bind="controller"`.
 * Actions are surfaced as **events** (`mark-as-read`, `mark-all-as-read`, `load-more`,
 * `tab-change`), not function props; the active tab is two-way via `v-model:activeTab`.
 */
export interface NotificationPanelProps {
  // — data (spread these from useNotifications via v-bind="controller") —
  notifications: NotificationLog[];
  unreadCount?: number;
  hasNextPage: boolean;
  loading?: boolean;
  error?: unknown;

  // — presentation —
  tabs?: NotificationTab[];
  title?: string;
}

/** Scope handed to the `#header` slot. */
export interface NotificationHeaderSlotProps {
  title?: string;
  unreadCount?: number;
  tabs: NotificationTab[];
  activeTab: string | undefined;
  selectTab: (value: string) => void;
  markAllAsRead: () => void | Promise<void>;
  /** trigger the panel's `close` event (the host owns the container) */
  close: () => void;
}

/** Scope handed to the body / `#tab-<value>` / `#item` slots. The callables emit panel events. */
export interface NotificationBodySlotProps {
  /** rows visible under the active tab (the tab's client predicate already applied) */
  notifications: NotificationLog[];
  /** emits `mark-as-read` for the given row */
  markAsRead: (n: NotificationLog) => void;
  /** emits `load-more` */
  loadMore: () => void;
  hasNextPage: boolean;
}
