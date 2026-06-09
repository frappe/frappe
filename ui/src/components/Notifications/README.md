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

With tabs and custom fields:

```vue
<NotificationPanel
  :fields="['name', 'subject', 'type', 'read', 'creation', 'severity']"
  :tabs="[
    { label: 'All' },
    { label: 'Unread', filterFn: (n) => !n.read, count: 'unread' },
    { label: 'Alerts', filters: { type: 'Alert' } },
  ]"
  :on-item-click="(n) => router.push(n.link)"
/>
```

## Props

| Prop | Type | Default | Description |
|---|---|---|---|
| `fields` | `string[]` | generic set | Notification Log fields to fetch. Add custom fields here so they reach `itemStyle` / slots. |
| `tabs` | `NotificationTab[]` | — | Tabs. Without it, a flat list is shown. |
| `showMarkAllRead` | `boolean` | `true` | Show the "Mark all as read" header button. |
| `showClose` | `boolean` | `true` | Show the "Close" header button (emits `close`). |
| `pageLength` | `number` | `20` | Page size; "Load more" appears when more exist. |
| `title` | `string` | `'Notifications'` | Header title. |
| `onItemClick` | `(n) => void` | — | Called when a row is clicked (in addition to the `item-click` event). |
| `itemStyle` | `(n) => NotificationItemStyle` | — | Resolve the leading visual per row (e.g. from a custom field). Falls back to the Notification Type's icon/color. |
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
| `leading` | `{ notification, style, isUnread }` | Replace a row's left visual (avatar/icon). |
| `item` | `{ notification, typeMeta }` | Replace the entire row. |
| `empty` | — | Replace the empty state. |

## Leading visual

Each row's leading visual is a frappe-ui `Avatar`, resolved as: `image` → `icon` (lucide) → `label`/initials, tinted by `color`. Drive it with `itemStyle`:

```ts
:item-style="(n) => ({ icon: 'alert-circle', color: 'red' })"
// or an image: { image: n.sender_avatar }
```

Color tokens: `blue`, `green`, `red`, `orange`, `yellow`, `gray`.

> The default icon render uses frappe-ui's `lucide-<name>` class. Because Tailwind cannot detect dynamically-built classes, an arbitrary icon name may not render in every host build. For guaranteed icons, use the `#leading` slot and render your own icon component:
> ```vue
> <template #leading="{ notification, style }">
>   <LucideAtSign v-if="style.icon === 'at-sign'" class="size-4" />
> </template>
> ```

## `useNotifications`

The composable behind the panel, for building a custom UI:

```ts
const {
  notifications,   // Ref<NotificationLog[]>
  unreadCount,     // Ref<number>
  hasNextPage,
  typeMeta,        // (type) => NotificationType | undefined
  markAsRead,      // (name) => Promise
  markAllAsRead,   // () => Promise
  markSeen,        // clears the unseen indicator
  reload,
  setFilters,      // (filters) => void
  loadMore,
} = useNotifications({ fields, pageLength, filters, socket })
```

## Types

- `NotificationLog` — a Notification Log row (custom fields included).
- `NotificationType` — `{ name, type_name?, icon?, color? }`.
- `NotificationItemStyle` — `{ icon?, color?, image?, label? }`.
- `NotificationTab`, `NotificationPanelProps`.

## Backend

Requires Frappe with the `Notification Type` doctype. The component reads the `Notification Log` list and calls these whitelisted methods:

- `notification_log.mark_as_read`, `notification_log.mark_all_as_read`
- `notification_log.trigger_indicator_hide`
- `notification_type.get_notification_types` (icon/color metadata)

Realtime updates listen on the `notification` event.
