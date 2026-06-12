import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { call, createListResource, createResource } from "frappe-ui";
import type { NotificationLog } from "./types";

const METHOD = "frappe.desk.doctype.notification_log.notification_log";

export const DEFAULT_FIELDS = [
  "name",
  "title",
  "description",
  "subject",
  "type",
  "app",
  "read",
  "from_user",
  "document_type",
  "document_name",
  "link",
  "creation",
];

export interface UseNotificationsOptions {
  fields?: string[];
  pageLength?: number;
  /** scope the feed to a single app — only notifications produced by that app are shown */
  appName?: string;
  /**
   * scope the feed to one recipient (`for_user`). Defaults to the logged-in user
   * (resolved from `frappe.auth.get_logged_user`). Pass it explicitly when the host already
   * knows the user (avoids a round-trip) or to view a specific user's feed — e.g. a demo.
   *
   * This matters because the panel must always show *one* user's notifications: Notification
   * Log's permission rules let an Administrator read *everyone's*, so without this filter an
   * admin session would see all users' notifications (and inflated counts).
   */
  currentUser?: string;
  filters?: Record<string, unknown>;
  socket?: {
    on: (event: string, cb: (...args: unknown[]) => void) => void;
    off?: (event: string, cb: (...args: unknown[]) => void) => void;
  };
}

export function useNotifications(options: UseNotificationsOptions = {}) {
  const fields = options.fields?.length ? options.fields : DEFAULT_FIELDS;
  const pageLength = options.pageLength ?? 20;
  const appName = options.appName;

  // app scope is a static equality filter on the denormalized `app` column, set when the
  // notification is created. Merged with the active tab's server filters below.
  const appFilter = appName ? { app: appName } : {};
  // tab/server filters (set by the panel) kept separate from the app scope so they merge
  const serverFilters = ref<Record<string, unknown>>(options.filters ?? {});

  // recipient scope: always restrict the feed to a single user's notifications. Resolved from
  // the logged-in user when not supplied (see the auto-resolve block near the bottom).
  const currentUser = ref<string | undefined>(options.currentUser);
  const userFilter = () =>
    currentUser.value ? { for_user: currentUser.value } : {};

  const list = createListResource({
    doctype: "Notification Log",
    fields,
    filters: { ...serverFilters.value, ...appFilter, ...userFilter() },
    orderBy: "creation desc",
    pageLength,
    // Persist the feed across mounts (and sessions, via localStorage). Reopening the panel
    // returns this same cached resource with its rows intact and revalidates in the
    // background, instead of starting empty and flashing the empty state. Keyed by scope so
    // different apps / users don't share a cache. Tab filters are applied via `update()`, so
    // they intentionally aren't part of the key (one feed resource, re-filtered in place).
    cache: [
      "notification_log_feed",
      appName ?? "all",
      options.currentUser ?? "self",
    ],
    auto: true,
  });

  // sender photos for the default avatar, keyed by user id; resolved lazily as rows load
  const userImages = ref<Record<string, string>>({});
  async function resolveUserImages(rows: NotificationLog[]) {
    const missing = [
      ...new Set(
        rows
          .map((n) => n.from_user)
          .filter((u): u is string => Boolean(u) && !(u in userImages.value))
      ),
    ];
    if (!missing.length) return;
    // mark as attempted so we don't refetch users without an image
    missing.forEach((u) => (userImages.value[u] = userImages.value[u] ?? ""));
    try {
      const users = (await call("frappe.client.get_list", {
        doctype: "User",
        filters: { name: ["in", missing] },
        fields: ["name", "user_image"],
        limit_page_length: 0,
      })) as Array<{ name: string; user_image?: string }>;
      for (const u of users)
        if (u.user_image) userImages.value[u.name] = u.user_image;
    } catch {
      /* avatars degrade to initials */
    }
  }

  const notifications = computed<NotificationLog[]>(() =>
    ((list.data as NotificationLog[]) || []).map((n) => ({
      ...n,
      from_user_image: n.from_user
        ? userImages.value[n.from_user] || undefined
        : undefined,
    }))
  );
  watch(
    () => list.data,
    (rows) => resolveUserImages((rows as NotificationLog[]) || []),
    { immediate: true }
  );

  // Unread count comes from the server (a COUNT over all of the user's matching rows),
  // not from the fetched page — counting `notifications.value` would cap at `pageLength`.
  // It is adjusted optimistically on mark-read for instant UI, then reconciled against the
  // server on reload / realtime / filter change.
  const unreadResource = createResource({
    url: "frappe.client.get_count",
    makeParams: () => ({
      doctype: "Notification Log",
      filters: {
        ...serverFilters.value,
        ...appFilter,
        ...userFilter(),
        read: 0,
      },
    }),
    auto: true,
  });
  function refreshUnreadCount() {
    unreadResource.reload();
  }
  const unreadCount = computed<number>(
    () => (unreadResource.data as number) ?? 0
  );
  const hasNextPage = computed(() => Boolean(list.hasNextPage));
  // true only while a fetch is in flight with nothing to show yet — lets the panel hold off
  // the empty state on a cold first load (a cached feed already has rows, so it stays false).
  const loading = computed(
    () =>
      Boolean(list.list?.loading) && !(list.data as NotificationLog[])?.length
  );

  async function markAsRead(name: string) {
    const n = (list.data as NotificationLog[])?.find((x) => x.name === name);
    if (n && !n.read) {
      n.read = 1; // optimistic
      const current = unreadResource.data as number;
      if (typeof current === "number" && current > 0)
        unreadResource.data = current - 1;
    }
    await call(`${METHOD}.mark_as_read`, { docname: name });
    refreshUnreadCount();
  }

  async function markAllAsRead() {
    (list.data as NotificationLog[])?.forEach((n) => (n.read = 1)); // optimistic
    unreadResource.data = 0;
    await call(`${METHOD}.mark_all_as_read`);
    refreshUnreadCount();
  }

  /** tell the backend the bell indicator was seen (clears the unseen dot) */
  function markSeen() {
    call(`${METHOD}.trigger_indicator_hide`).catch(() => {});
  }

  function reload() {
    list.reload();
  }

  function applyFilters() {
    list.update({
      filters: { ...serverFilters.value, ...appFilter, ...userFilter() },
    });
    list.reload();
    refreshUnreadCount();
  }

  /** set the active tab's server-side filters; the app scope (if any) is always preserved */
  function setServerFilters(filters: Record<string, unknown>) {
    serverFilters.value = filters || {};
    applyFilters();
  }

  // Resolve the logged-in user when the host didn't supply one, then re-scope the feed.
  // Declared after applyFilters so the watch can call it. For a non-admin session the
  // permission query already scopes to the user, so this only changes what an admin sees;
  // the initial (unscoped) load self-corrects once the user resolves. We watch the resource's
  // data (not onSuccess) because a *cached* result skips onSuccess on later mounts.
  if (!options.currentUser) {
    const loggedUser = createResource({
      url: "frappe.auth.get_logged_user",
      auto: true,
      cache: "notification_current_user",
    });
    watch(
      () => loggedUser.data as string | undefined,
      (user) => {
        if (!user || user === currentUser.value) return;
        currentUser.value = user;
        applyFilters();
      },
      { immediate: true }
    );
  }

  const onRealtime = () => {
    reload();
    refreshUnreadCount();
  };
  onMounted(() => {
    options.socket?.on("notification", onRealtime);
  });
  onBeforeUnmount(() => {
    options.socket?.off?.("notification", onRealtime);
  });

  return {
    list,
    notifications,
    unreadCount,
    hasNextPage,
    loading,
    markAsRead,
    markAllAsRead,
    markSeen,
    reload,
    setServerFilters,
    loadMore: () => list.next?.(),
  };
}

export type UseNotifications = ReturnType<typeof useNotifications>;
