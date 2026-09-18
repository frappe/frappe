import {
  computed,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from "vue";
import { call, createResource } from "frappe-ui";
import { countDocuments, listDocuments } from "../../api";
import { usePagedList } from "../../composables/usePagedList";
import type {
  NotificationLog,
  NotificationStore,
  NotificationTab,
  UseNotificationsOptions,
} from "./types";

const METHOD = "frappe.desk.doctype.notification_log.notification_log";
const DOCTYPE = "Notification Log";

export function useNotifications(
  options: UseNotificationsOptions = {}
): NotificationStore {
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
  const scopedFilters = () => ({
    ...serverFilters.value,
    ...appFilter,
    ...userFilter(),
  });

  // always fetch every column: Custom Fields flow through automatically, and trimming
  // columns was never real fetch control (the row is read from the table regardless).
  const list = usePagedList<NotificationLog>(
    DOCTYPE,
    () => ({ fields: ["*"], filters: scopedFilters(), order_by: "creation desc" }),
    { pageLength }
  );
  void list.reload();

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
      const { data: users } = await listDocuments<{ name: string; user_image?: string }>(
        "User",
        {
          filters: { name: ["in", missing] },
          fields: ["name", "user_image"],
          limit: missing.length,
        }
      );
      for (const u of users)
        if (u.user_image) userImages.value[u.name] = u.user_image;
    } catch {
      /* avatars degrade to initials */
    }
  }

  const notifications = computed<NotificationLog[]>(() =>
    list.rows.value.map((n) => ({
      ...n,
      from_user_image: n.from_user
        ? userImages.value[n.from_user] || undefined
        : undefined,
    }))
  );
  watch(list.rows, (rows) => resolveUserImages(rows), { immediate: true });

  // Unread count comes from the server (a COUNT over all of the user's matching rows),
  // not from the fetched page — counting `notifications.value` would cap at `pageLength`.
  // It is adjusted optimistically on mark-read for instant UI, then reconciled against the
  // server on reload / realtime / filter change.
  const unread = ref(0);
  const unreadError = ref<unknown>(null);
  async function refreshUnreadCount() {
    try {
      const { data } = await countDocuments(DOCTYPE, {
        filters: { ...scopedFilters(), read: 0 },
      });
      unread.value = data ?? 0;
      unreadError.value = null;
    } catch (failure) {
      unreadError.value = failure;
    }
  }
  void refreshUnreadCount();
  const unreadCount = computed<number>(() => unread.value);
  const hasNextPage = computed(() => list.hasNextPage.value);
  // true only while a fetch is in flight with nothing to show yet — lets the panel hold off
  // the empty state on a cold first load
  const loading = computed(
    () => list.loading.value && !list.rows.value.length
  );
  // surfaced to the panel's #error slot; null while healthy
  const error = computed<unknown>(
    () => list.error.value ?? unreadError.value ?? null
  );

  async function markAsRead(name: string) {
    const n = list.rows.value.find((x) => x.name === name);
    if (n && !n.read) {
      n.read = 1; // optimistic
      if (unread.value > 0) unread.value -= 1;
    }
    await call(`${METHOD}.mark_as_read`, { docname: name });
    void refreshUnreadCount();
  }

  async function markAllAsRead() {
    list.rows.value.forEach((n) => (n.read = 1)); // optimistic
    unread.value = 0;
    await call(`${METHOD}.mark_all_as_read`);
    void refreshUnreadCount();
  }

  /** tell the backend the bell indicator was seen (clears the unseen dot) */
  function markSeen() {
    call(`${METHOD}.trigger_indicator_hide`).catch(() => {});
  }

  function reload() {
    void list.reload();
  }

  function applyFilters() {
    reload();
    void refreshUnreadCount();
  }

  /** set arbitrary server-side filters; the app scope (if any) is always preserved */
  function setFilters(filters: Record<string, unknown>) {
    serverFilters.value = filters || {};
    applyFilters();
  }

  /** apply a tab's filter when it activates: object filters re-query the server, function
   *  filters are client-side (handled by the panel) so they clear the server filter here. */
  function filterByTab(tab?: NotificationTab) {
    const f = tab?.filter;
    setFilters(f && typeof f !== "function" ? f : {});
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
    void refreshUnreadCount();
  };
  onMounted(() => {
    options.socket?.on("notification", onRealtime);
  });
  onBeforeUnmount(() => {
    options.socket?.off?.("notification", onRealtime);
  });

  // Returned as a `reactive` object so the panel can spread it with `v-bind="controller"`:
  // `v-bind` does not unwrap refs nested in a plain object, but `reactive` unwraps them, so
  // each member binds as a live value. For a custom UI, read members off the returned object
  // (e.g. `controller.notifications`) rather than destructuring, which would drop reactivity.
  return reactive({
    notifications,
    unreadCount,
    hasNextPage,
    loading,
    error,
    markAsRead,
    markAllAsRead,
    markSeen,
    reload,
    loadMore: () => void list.loadMore(),
    setFilters,
    filterByTab,
  }) as NotificationStore;
}
