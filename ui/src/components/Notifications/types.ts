export interface NotificationLog {
  name: string
  subject?: string
  type?: string
  read: number | boolean
  from_user?: string
  document_type?: string
  document_name?: string
  link?: string
  creation: string
  // app-specific Custom Fields flow through untyped
  [key: string]: unknown
}

export interface NotificationType {
  name: string
  type_name?: string
  icon?: string
  color?: string
}

/** Controls the leading visual (a frappe-ui Avatar) of a notification row. */
export interface NotificationItemStyle {
  /** lucide icon name rendered inside the avatar (e.g. "at-sign") */
  icon?: string
  /** semantic color token (blue/green/red/orange/yellow/gray) */
  color?: string
  /** image URL — when set, the avatar shows this image */
  image?: string
  /** fallback initials/label for the avatar */
  label?: string
}

export interface NotificationTab {
  label: string
  /** server-side filters applied to the Notification Log list query */
  filters?: Record<string, unknown>
  /** client-side predicate applied to the already-fetched rows */
  filterFn?: (n: NotificationLog) => boolean
  /** badge next to the tab label */
  count?: 'unread' | ((items: NotificationLog[]) => number)
}

export interface NotificationPanelProps {
  /** Notification Log fields to fetch; defaults include the generic set. Append custom fields here. */
  fields?: string[]
  tabs?: NotificationTab[]
  showMarkAllRead?: boolean
  showClose?: boolean
  pageLength?: number
  title?: string
  /** host routing hook; called (in addition to @item-click) when a row is clicked */
  onItemClick?: (n: NotificationLog) => void
  /** derive the leading visual per row, e.g. from a custom `severity` field or the sender's avatar; falls back to Notification Type metadata */
  itemStyle?: (n: NotificationLog) => NotificationItemStyle
  /** a frappe-ui / socket.io socket; if provided, the panel live-reloads on the `notification` event */
  socket?: {
    on: (event: string, cb: (...args: unknown[]) => void) => void
    off?: (event: string, cb: (...args: unknown[]) => void) => void
  }
}
