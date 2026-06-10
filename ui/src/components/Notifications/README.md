# NotificationPanel

A Vue notification panel for the user's **Notification Log** (the bell feed). It fetches the current user's notifications, renders them as a list, marks them read, supports tabs/filtering and pagination, and live-updates over realtime.

It renders the panel body only — the host provides the trigger (bell button) and container (popover, dialog, sidebar, page).

## Usage

```vue
<script setup lang="ts">
import { NotificationPanel } from '@framework/ui'
import { socket } from '@/socket' // optional
</script>

<template>
  <NotificationPanel :socket="socket" @item-click="goTo" />
</template>
```

Scoped to a single app:

```vue
<NotificationPanel app-name="crm" />
```

With tabs and custom fields:

```vue
<NotificationPanel
  :fields="['name', 'title', 'description', 'type', 'read', 'creation', 'severity']"
  :tabs="[
    { label: 'All' },
    { label: 'Unread', filterFn: (n) => !n.read, count: 'unread' },
    { label: 'Alerts', filters: { type: 'Alert' } },
  ]"
  :on-item-click="(n) => router.push(n.link)"
/>
```

### App scoping

`appName` filters the feed to notifications whose `document_type` belongs to that app (resolved server-side from the doctype→app map). Notes:

- A notification with **no** `document_type` cannot be scoped and is excluded when `appName` is set.
- Apps with many doctypes produce a large `document_type IN (...)` query; fine for per-user notification volumes.
- Omitting `appName` shows all of the user's notifications (unchanged behavior).

## Props

| Prop | Type | Default | Description |
|---|---|---|---|
| `appName` | `string` | — | Scope the feed to one app. Only notifications whose `document_type` belongs to that app are shown. Tabs filter *within* this scope. |
| `fields` | `string[]` | generic set | Notification Log fields to fetch. Add custom fields here so they reach the `icon` resolver / slots. |
| `tabs` | `NotificationTab[]` | — | Tabs. Without it, a flat list is shown. |
| `showMarkAllRead` | `boolean` | `true` | Show the "Mark all as read" header button. |
| `showClose` | `boolean` | `true` | Show the "Close" header button (emits `close`). |
| `pageLength` | `number` | `20` | Page size; "Load more" appears when more exist. |
| `title` | `string` | `'Notifications'` | Header title. |
| `onItemClick` | `(n) => void` | — | Called when a row is clicked (in addition to the `item-click` event). |
| `icon` | `(n) => string \| Component \| undefined` | — | Resolve a row's leading visual: return a lucide/feather icon **name** (string) or a **Component**. Return `undefined` (the default) to show the sender's avatar. |
| `socket` | `{ on, off? }` | — | A socket.io socket. When provided, the panel reloads on the `notification` event. |

A tab is `{ label, filters?, filterFn?, count? }`:
- `filters` — server-side filters applied to the list query.
- `filterFn` — client-side predicate applied to already-fetched rows.
- `count` — `'unread'` or `(items) => number`; shown as a badge.

## Events

| Event | Payload | When |
|---|---|---|
| `item-click` | `notification` | A row is clicked (the row is also marked read). |
| `mark-all-read` | — | "Mark all as read" clicked. |
| `close` | — | "Close" clicked. |
| `update:unread-count` | `number` | Unread count changes. |

## Slots

| Slot | Props | Description |
|---|---|---|
| `header` | `{ unreadCount }` | Replace the whole header. |
| `item` | `{ notification }` | Replace the entire row. |
| `empty` | — | Replace the empty state. |

## Leading visual

By default each row shows the **sender's avatar** (`from_user`'s photo, falling back to
initials). Override per row with the `icon` resolver — return a string (rendered via
frappe-ui's icon component) or your own Component:

```ts
// a named icon for system notifications, sender avatar for everything else
:icon="(n) => (n.type === 'Alert' ? 'alert-circle' : undefined)"

// or a fully custom component (receives the row as a `notification` prop)
:icon="(n) => MyIcon"
```

`Notification Type` carries no icon/color — presentation lives entirely in the host UI, so
string-icon names must exist in the host's icon set. For guaranteed rendering, return a
Component instead of a string.

## `useNotifications`

The composable behind the panel, for building a custom UI:

```ts
const {
  notifications,   // Ref<NotificationLog[]> (each row carries a resolved from_user_image)
  unreadCount,     // Ref<number>
  hasNextPage,
  markAsRead,      // (name) => Promise
  markAllAsRead,   // () => Promise
  markSeen,        // clears the unseen indicator
  reload,
  setServerFilters,// (filters) => void — merged with the app scope
  loadMore,
} = useNotifications({ fields, pageLength, appName, filters, socket })
```

## Types

- `NotificationLog` — a Notification Log row (`title`/`description` + custom fields included).
- `NotificationType` — `{ name, type_name?, enabled? }` (categorical only).
- `NotificationIcon` — `string | Component`.
- `NotificationTab`, `NotificationPanelProps`.

## Backend

Requires Frappe with the `Notification Type` doctype. The component reads the `Notification Log` list and calls these whitelisted methods:

- `notification_log.mark_as_read`, `notification_log.mark_all_as_read`
- `notification_log.trigger_indicator_hide`
- `notification_log.get_app_doctypes` (when `appName` is set)
- `frappe.client.get_list` on `User` (to resolve sender avatar images)

Realtime updates listen on the `notification` event.
