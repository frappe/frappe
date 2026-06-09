import { computed, onBeforeUnmount, onMounted } from 'vue'
import { call, createListResource, createResource } from 'frappe-ui'
import type { NotificationLog, NotificationType } from './types'

const METHOD = 'frappe.desk.doctype.notification_log.notification_log'
const TYPE_METHOD =
  'frappe.desk.doctype.notification_type.notification_type.get_notification_types'

export const DEFAULT_FIELDS = [
  'name',
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
  filters?: Record<string, unknown>
  socket?: {
    on: (event: string, cb: (...args: unknown[]) => void) => void
    off?: (event: string, cb: (...args: unknown[]) => void) => void
  }
}

export function useNotifications(options: UseNotificationsOptions = {}) {
  const fields = options.fields?.length ? options.fields : DEFAULT_FIELDS
  const pageLength = options.pageLength ?? 20

  const list = createListResource({
    doctype: 'Notification Log',
    fields,
    filters: options.filters ?? {},
    orderBy: 'creation desc',
    pageLength,
    auto: true,
  })

  // type metadata (icon / color) keyed by Notification Type name
  const types = createResource({
    url: TYPE_METHOD,
    auto: true,
    cache: 'notification_types',
    transform(rows: NotificationType[]) {
      const map: Record<string, NotificationType> = {}
      for (const row of rows || []) map[row.name] = row
      return map
    },
  })

  const notifications = computed<NotificationLog[]>(
    () => (list.data as NotificationLog[]) || [],
  )
  const unreadCount = computed(
    () => notifications.value.filter((n) => !n.read).length,
  )
  const hasNextPage = computed(() => Boolean(list.hasNextPage))

  function typeMeta(type?: string): NotificationType | undefined {
    if (!type || !types.data) return undefined
    return (types.data as Record<string, NotificationType>)[type]
  }

  async function markAsRead(name: string) {
    const n = notifications.value.find((x) => x.name === name)
    if (n && !n.read) n.read = 1 // optimistic
    await call(`${METHOD}.mark_as_read`, { docname: name })
  }

  async function markAllAsRead() {
    notifications.value.forEach((n) => (n.read = 1)) // optimistic
    await call(`${METHOD}.mark_all_as_read`)
  }

  /** tell the backend the bell indicator was seen (clears the unseen dot) */
  function markSeen() {
    call(`${METHOD}.trigger_indicator_hide`).catch(() => {})
  }

  function reload() {
    list.reload()
  }

  function setFilters(filters: Record<string, unknown>) {
    list.update({ filters })
    list.reload()
  }

  const onRealtime = () => reload()
  onMounted(() => {
    options.socket?.on('notification', onRealtime)
  })
  onBeforeUnmount(() => {
    options.socket?.off?.('notification', onRealtime)
  })

  return {
    list,
    types,
    notifications,
    unreadCount,
    hasNextPage,
    typeMeta,
    markAsRead,
    markAllAsRead,
    markSeen,
    reload,
    setFilters,
    loadMore: () => list.next?.(),
  }
}

export type UseNotifications = ReturnType<typeof useNotifications>
