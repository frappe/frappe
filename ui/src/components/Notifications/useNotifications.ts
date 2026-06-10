import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { call, createListResource, createResource } from 'frappe-ui'
import type { NotificationLog } from './types'

const METHOD = 'frappe.desk.doctype.notification_log.notification_log'

export const DEFAULT_FIELDS = [
  'name',
  'title',
  'description',
  'subject',
  'type',
  'read',
  'from_user',
  'document_type',
  'document_name',
  'link',
  'creation',
]

export interface UseNotificationsOptions {
  fields?: string[]
  pageLength?: number
  /** scope the feed to a single app — only notifications about that app's documents are shown */
  appName?: string
  filters?: Record<string, unknown>
  socket?: {
    on: (event: string, cb: (...args: unknown[]) => void) => void
    off?: (event: string, cb: (...args: unknown[]) => void) => void
  }
}

export function useNotifications(options: UseNotificationsOptions = {}) {
  const fields = options.fields?.length ? options.fields : DEFAULT_FIELDS
  const pageLength = options.pageLength ?? 20
  const appName = options.appName

  // tab/server filters (set by the panel) kept separate from the app scope so they merge
  const serverFilters = ref<Record<string, unknown>>(options.filters ?? {})
  // null until resolved (used to gate the first load when appName is set)
  const appDoctypes = ref<string[] | null>(appName ? null : [])

  function effectiveFilters(): Record<string, unknown> {
    if (!appName) return serverFilters.value
    return { ...serverFilters.value, document_type: ['in', appDoctypes.value ?? []] }
  }

  const list = createListResource({
    doctype: 'Notification Log',
    fields,
    filters: appName ? {} : (options.filters ?? {}),
    orderBy: 'creation desc',
    pageLength,
    auto: !appName, // when scoped to an app, defer until its doctypes resolve
  })

  // sender photos for the default avatar, keyed by user id; resolved lazily as rows load
  const userImages = ref<Record<string, string>>({})
  async function resolveUserImages(rows: NotificationLog[]) {
    const missing = [
      ...new Set(
        rows
          .map((n) => n.from_user)
          .filter((u): u is string => Boolean(u) && !(u in userImages.value)),
      ),
    ]
    if (!missing.length) return
    // mark as attempted so we don't refetch users without an image
    missing.forEach((u) => (userImages.value[u] = userImages.value[u] ?? ''))
    try {
      const users = (await call('frappe.client.get_list', {
        doctype: 'User',
        filters: { name: ['in', missing] },
        fields: ['name', 'user_image'],
        limit_page_length: 0,
      })) as Array<{ name: string; user_image?: string }>
      for (const u of users) if (u.user_image) userImages.value[u.name] = u.user_image
    } catch {
      /* avatars degrade to initials */
    }
  }

  const notifications = computed<NotificationLog[]>(() =>
    ((list.data as NotificationLog[]) || []).map((n) => ({
      ...n,
      from_user_image: n.from_user ? userImages.value[n.from_user] || undefined : undefined,
    })),
  )
  watch(
    () => list.data,
    (rows) => resolveUserImages((rows as NotificationLog[]) || []),
    { immediate: true },
  )

  // Unread count comes from the server (a COUNT over all of the user's matching rows),
  // not from the fetched page — counting `notifications.value` would cap at `pageLength`.
  // It is adjusted optimistically on mark-read for instant UI, then reconciled against the
  // server on reload / realtime / filter change.
  const unreadResource = createResource({
    url: 'frappe.client.get_count',
    makeParams: () => ({
      doctype: 'Notification Log',
      filters: { ...effectiveFilters(), read: 0 },
    }),
    auto: !appName, // when scoped to an app, defer until its doctypes resolve
  })
  function refreshUnreadCount() {
    unreadResource.reload()
  }
  const unreadCount = computed<number>(() => (unreadResource.data as number) ?? 0)
  const hasNextPage = computed(() => Boolean(list.hasNextPage))

  async function markAsRead(name: string) {
    const n = (list.data as NotificationLog[])?.find((x) => x.name === name)
    if (n && !n.read) {
      n.read = 1 // optimistic
      const current = unreadResource.data as number
      if (typeof current === 'number' && current > 0) unreadResource.data = current - 1
    }
    await call(`${METHOD}.mark_as_read`, { docname: name })
    refreshUnreadCount()
  }

  async function markAllAsRead() {
    ;(list.data as NotificationLog[])?.forEach((n) => (n.read = 1)) // optimistic
    unreadResource.data = 0
    await call(`${METHOD}.mark_all_as_read`)
    refreshUnreadCount()
  }

  /** tell the backend the bell indicator was seen (clears the unseen dot) */
  function markSeen() {
    call(`${METHOD}.trigger_indicator_hide`).catch(() => {})
  }

  function reload() {
    list.reload()
  }

  function applyFilters() {
    list.update({ filters: effectiveFilters() })
    list.reload()
    refreshUnreadCount()
  }

  /** set the active tab's server-side filters; the app scope (if any) is always preserved */
  function setServerFilters(filters: Record<string, unknown>) {
    serverFilters.value = filters || {}
    // wait for the app scope to resolve before the first query
    if (!appName || appDoctypes.value !== null) applyFilters()
  }

  // resolve the app's doctypes, then apply the scope and load. Watching the
  // resource's data (not just onSuccess) means a *cached* result — which skips
  // onSuccess on later mounts — still kicks off the initial load. Declared here,
  // after the resources/functions above, so the immediate watch can safely call
  // applyFilters() during setup without hitting an uninitialized binding.
  if (appName) {
    const appDoctypesResource = createResource({
      url: `${METHOD}.get_app_doctypes`,
      params: { app: appName },
      auto: true,
      cache: ['notification_app_doctypes', appName],
    })
    watch(
      () => appDoctypesResource.data as string[] | undefined,
      (doctypes) => {
        if (!doctypes) return
        appDoctypes.value = doctypes
        applyFilters()
      },
      { immediate: true },
    )
  }

  const onRealtime = () => {
    reload()
    refreshUnreadCount()
  }
  onMounted(() => {
    options.socket?.on('notification', onRealtime)
  })
  onBeforeUnmount(() => {
    options.socket?.off?.('notification', onRealtime)
  })

  return {
    list,
    notifications,
    unreadCount,
    hasNextPage,
    markAsRead,
    markAllAsRead,
    markSeen,
    reload,
    setServerFilters,
    loadMore: () => list.next?.(),
  }
}

export type UseNotifications = ReturnType<typeof useNotifications>
