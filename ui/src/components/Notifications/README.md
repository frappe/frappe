# NotificationPanel

A Vue notification panel for the user's **Notification Log** (the bell feed). It fetches the current user's notifications, renders them as a list, marks them read, supports tabs/filtering and pagination, and live-updates over realtime.

It renders the panel body only — the host provides the trigger (bell button) and container (popover, dialog, sidebar, page).

## Usage

```vue
<script setup lang="ts">
import { NotificationPanel } from "@framework/ui";
import { socket } from "@/socket"; // optional
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
  :fields="[
    'name',
    'title',
    'description',
    'type',
    'read',
    'creation',
    'severity',
  ]"
  :tabs="[
    { label: 'All' },
    { label: 'Unread', filterFn: (n) => !n.read, count: 'unread' },
    { label: 'Alerts', filters: { type: 'Alert' } },
  ]"
  :on-item-click="(n) => router.push(n.link)"
/>
```

### App scoping

`appName` filters the feed to notifications produced by that app, via a direct equality filter on the Notification Log `app` column. The owning app is recorded **when the notification is created** (set explicitly by the producer, or derived from the reference document), so scoping reflects the _producing_ app — not whatever app happens to own the referenced document. Notes:

- A notification whose `app` couldn't be resolved (no/unknown reference document and no explicit app) is **global-only** — it shows in an unscoped panel but in no app-scoped panel.
- Scoping is a single indexed `app = appName` filter (no doctype→app resolution round-trip), so the panel loads without a pre-query.
- Omitting `appName` shows all of the user's notifications (unchanged behavior).

## Props

| Prop              | Type                                      | Default           | Description                                                                                                                                                                                                           |
| ----------------- | ----------------------------------------- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `appName`         | `string`                                  | —                 | Scope the feed to one app. Only notifications produced by that app (matched on the `app` column) are shown. Tabs filter _within_ this scope.                                                                          |
| `currentUser`     | `string`                                  | logged-in user    | Recipient to scope the feed to (`for_user`). Defaults to the logged-in user. Pass it to skip a lookup, or to view a specific user's feed. Without it an Administrator session would see _every_ user's notifications. |
| `fields`          | `string[]`                                | generic set       | Notification Log fields to fetch. Add custom fields here so they reach the `icon` resolver / slots.                                                                                                                   |
| `tabs`            | `NotificationTab[]`                       | —                 | Tabs. Without it, a flat list is shown.                                                                                                                                                                               |
| `showMarkAllRead` | `boolean`                                 | `true`            | Show the "Mark all as read" header button.                                                                                                                                                                            |
| `showClose`       | `boolean`                                 | `true`            | Show the "Close" header button (emits `close`).                                                                                                                                                                       |
| `pageLength`      | `number`                                  | `20`              | Page size; "Load more" appears when more exist.                                                                                                                                                                       |
| `title`           | `string`                                  | `'Notifications'` | Header title.                                                                                                                                                                                                         |
| `onItemClick`     | `(n) => void`                             | —                 | Called when a row is clicked (in addition to the `item-click` event).                                                                                                                                                 |
| `icon`            | `(n) => string \| Component \| undefined` | —                 | Resolve a row's leading visual: return a Lucide icon **name** (string, e.g. `'lucide-alert-circle'` or `'alert-circle'`) or a **Component**. Return `undefined` (the default) to show the sender's avatar.            |
| `socket`          | `{ on, off? }`                            | —                 | A socket.io socket. When provided, the panel reloads on the `notification` event.                                                                                                                                     |

A tab is `{ label, filters?, filterFn?, count? }`:

- `filters` — server-side filters applied to the list query.
- `filterFn` — client-side predicate applied to already-fetched rows.
- `count` — `'unread'` or `(items) => number`; shown as a badge.

## Events

| Event                 | Payload        | When                                            |
| --------------------- | -------------- | ----------------------------------------------- |
| `item-click`          | `notification` | A row is clicked (the row is also marked read). |
| `mark-all-read`       | —              | "Mark all as read" clicked.                     |
| `close`               | —              | "Close" clicked.                                |
| `update:unread-count` | `number`       | Unread count changes.                           |

## Slots

| Slot     | Props              | Description               |
| -------- | ------------------ | ------------------------- |
| `header` | `{ unreadCount }`  | Replace the whole header. |
| `item`   | `{ notification }` | Replace the entire row.   |
| `empty`  | —                  | Replace the empty state.  |

## Leading visual

By default each row shows the **sender's avatar** (`from_user`'s photo, falling back to
initials). Override per row with the `icon` resolver — return a **Lucide icon name**
(rendered via frappe-ui's `lucide-*` icon utility, the same mechanism `Button` uses for
string icons) or your own Component:

```ts
// a named Lucide icon for system notifications, sender avatar for everything else
// (the `lucide-` prefix is optional: 'lucide-alert-circle' and 'alert-circle' both work)
:icon="(n) => (n.type === 'Alert' ? 'lucide-alert-circle' : undefined)"

// or a fully custom component (receives the row as a `notification` prop)
:icon="(n) => MyIcon"
```

`Notification Type` carries no icon/color — presentation lives entirely in the host UI, so
a string name must be a valid Lucide icon. For guaranteed rendering, return a Component
instead of a string.

## `useNotifications`

The composable behind the panel, for building a custom UI:

```ts
const {
  notifications, // Ref<NotificationLog[]> (each row carries a resolved from_user_image)
  unreadCount, // Ref<number>
  hasNextPage,
  markAsRead, // (name) => Promise
  markAllAsRead, // () => Promise
  markSeen, // clears the unseen indicator
  reload,
  setServerFilters, // (filters) => void — merged with the app scope
  loadMore,
} = useNotifications({
  fields,
  pageLength,
  appName,
  currentUser,
  filters,
  socket,
});
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
- `frappe.client.get_count` / `frappe.client.get_list` on `Notification Log` (feed + unread count; always scoped to the recipient via `for_user`, and by the `app` column when `appName` is set)
- `frappe.auth.get_logged_user` (to resolve the recipient when `currentUser` isn't passed)
- `frappe.client.get_list` on `User` (to resolve sender avatar images)

Realtime updates listen on the `notification` event.
