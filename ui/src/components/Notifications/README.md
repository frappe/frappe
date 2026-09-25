# NotificationPanel

A Vue notification panel for the user's **Notification Log** (the bell feed). It renders a
list of the current user's notifications, marks them read, supports tabs/filtering and
pagination, and live-updates over realtime.

The component is **UI only**. Data is a plugin the host owns: call `useNotifications()` to get
a controller, then spread it onto the panel with `v-bind`. The host also provides the trigger
(bell button) and the container (popover, dialog, sidebar, page) — the panel renders the body.

## Usage

```vue
<script setup lang="ts">
import { NotificationPanel, useNotifications } from "@framework/ui";
import { socket } from "@/socket"; // optional

const controller = useNotifications({ socket });
</script>

<template>
  <NotificationPanel
    v-bind="controller"
    @mark-as-read="(n) => controller.markAsRead(n.name)"
    @mark-all-as-read="controller.markAllAsRead"
    @load-more="controller.loadMore"
    @tab-change="controller.filterByTab"
  />
</template>
```

`v-bind="controller"` spreads the controller's **data** members as props (the controller is a
`reactive` object, so each binds as a live value — don't destructure it). **Actions are events**,
not props: wire `@mark-as-read` / `@mark-all-as-read` / `@load-more` / `@tab-change` to the
controller's verbs (`@tab-change` carries the active tab; `filterByTab` resolves its filter).
The active tab is two-way via `v-model:activeTab` (optional).

Scoped to a single app, with tabs:

```vue
<script setup lang="ts">
import { ref } from "vue";

const controller = useNotifications({ appName: "crm", socket });
const tabs = [
  { label: "All", value: "all" },
  { label: "Unread", value: "unread", filter: (n) => !n.read, count: "unread" },
  { label: "Alerts", value: "alerts", filter: { type: "Alert" } },
];
const activeTab = ref("all"); // optional: read/control the active tab
</script>

<template>
  <NotificationPanel
    v-bind="controller"
    :tabs="tabs"
    v-model:activeTab="activeTab"
    @mark-as-read="(n) => controller.markAsRead(n.name)"
    @mark-all-as-read="controller.markAllAsRead"
    @load-more="controller.loadMore"
    @tab-change="controller.filterByTab"
  />
</template>
```

### App scoping

`appName` filters the feed to notifications produced by that app, via a direct equality filter
on the Notification Log `app` column. The owning app is recorded **when the notification is
created** (set explicitly by the producer, or derived from the reference document), so scoping
reflects the _producing_ app — not whatever app owns the referenced document.

- A notification whose `app` couldn't be resolved is **global-only** — it shows in an unscoped
  panel but in no app-scoped panel.
- Scoping is a single indexed `app = appName` filter (no doctype→app resolution round-trip).
- Omitting `appName` shows all of the user's notifications.

### Marking the feed as seen

The panel does not clear the bell's unseen indicator itself — the host owns the bell. Call
`controller.markSeen()` when you open the panel.

## Props

The panel takes **data** props — spread the controller's data members via `v-bind="controller"`.
Actions are events (below), not props. The presentation props are set directly.

| Prop                | Type                             | Description                                                        |
| ------------------- | -------------------------------- | ------------------------------------------------------------------ |
| `tabs`              | `NotificationTab[]`              | Tabs. Without it, a flat list is shown.                            |
| `title`             | `string` (`'Notifications'`)     | Header title.                                                      |
| `v-model:activeTab` | `string`                         | Active tab value (two-way; defaults to the first tab).             |
| _controller data_   | spread via `v-bind="controller"` | `notifications`, `unreadCount`, `hasNextPage`, `loading`, `error`. |

A tab is `{ label, value?, filter?, count? }`:

- `value` — stable key (used for the `#tab-<value>` slot); defaults to `label`.
- `filter` — an **object** is a server-side filter (re-queries, affects counts/pagination); a
  **function** `(n) => boolean` is a client-side predicate over already-fetched rows.
- `count` — `'unread'` or `(items) => number`; surfaced inline in the tab label.

> **Wiring note:** object (server) filters only take effect when `@tab-change` is wired (to
> `filterByTab`, or your own `setFilters`). Function filters are applied client-side by the
> panel and work without any listener. So if every tab uses a function filter (or no filter),
> `@tab-change` is optional; wire it as soon as one tab uses an object filter.

## Events

Actions are events; wire them to the controller's verbs.

| Event              | Payload           | When                                           |
| ------------------ | ----------------- | ---------------------------------------------- |
| `mark-as-read`     | `NotificationLog` | A row is clicked / activated.                  |
| `mark-all-as-read` | —                 | "Mark all as read" is clicked.                 |
| `load-more`        | —                 | "Load more" is clicked.                        |
| `tab-change`       | `NotificationTab` | The active tab changes. Wire to `filterByTab`. |
| `close`            | —                 | "Close" is clicked.                            |

Routing / side-effects live in the `@mark-as-read` handler (or wherever you call
`controller.markAsRead` from your own UI).

## Slots

Every slot's default is the standard markup, so passing none renders the default panel.

| Slot          | Props                                                                      | Description                    |
| ------------- | -------------------------------------------------------------------------- | ------------------------------ |
| `header`      | `{ title, unreadCount, tabs, activeTab, selectTab, markAllAsRead, close }` | Replace the whole header.      |
| _default_     | `{ notifications, markAsRead, loadMore, hasNextPage }`                     | Replace the whole body.        |
| `tab-<value>` | same as default                                                            | Replace the body for one tab.  |
| `item`        | `{ notification, markAsRead }`                                             | Replace a single row.          |
| `empty`       | —                                                                          | Replace the empty state.       |
| `error`       | `{ error }`                                                                | Shown only on a fetch failure. |

The `markAsRead` slot prop takes the row (`markAsRead(notification)`) and emits `mark-as-read`.

`NotificationItem` exposes the canonical `#prefix` (leading visual), default (title),
`#description`, and `#suffix` (meta) slots — each scoped with `{ notification }`. `#prefix`
defaults to the sender's avatar.

### Example

A custom body for one tab plus a custom empty state — every other slot keeps its default:

```vue
<template>
  <NotificationPanel
    v-bind="controller"
    :tabs="tabs"
    @mark-as-read="(n) => controller.markAsRead(n.name)"
    @tab-change="controller.filterByTab"
  >
    <!-- replace the body for the Alerts tab (value: "alerts") -->
    <template #tab-alerts="{ notifications, markAsRead }">
      <button
        v-for="n in notifications"
        :key="n.name"
        class="block w-full px-4 py-3 text-left hover:bg-surface-gray-1"
        @click="markAsRead(n)"
      >
        <span class="text-ink-amber-3">⚠</span> <span v-html="n.title" />
      </button>
    </template>

    <!-- custom empty state -->
    <template #empty>
      <div class="py-12 text-center text-ink-gray-5">
        You're all caught up 🎉
      </div>
    </template>
  </NotificationPanel>
</template>
```

## `useNotifications`

The data plugin behind the panel.

```ts
const controller = useNotifications({
  appName, // scope to one app (optional)
  currentUser, // recipient scope; defaults to the logged-in user
  filters, // initial server-side filters
  pageLength, // default 20
  socket, // a frappe-ui / socket.io socket; live-reloads on the `notification` event
});

// controller (a reactive object):
// notifications, unreadCount, hasNextPage, loading, error,
// markAsRead, markAllAsRead, markSeen, reload, loadMore, setFilters, filterByTab
```

The feed is always fetched with `["*"]`, so app-specific Custom Fields flow through to
`NotificationLog` rows (and your slots) without configuration.

## Types

- `NotificationLog` — a Notification Log row (custom fields included). `title`/`description`
  are HTML sanitized by the backend at write time.
- `NotificationTab`, `NotificationStore`, `NotificationSocket`, `UseNotificationsOptions`,
  `NotificationPanelProps`, `NotificationHeaderSlotProps`, `NotificationBodySlotProps`.

## Backend

Requires Frappe with the `Notification Type` doctype. The controller reads the `Notification
Log` list and calls these whitelisted methods:

- `notification_log.mark_as_read`, `notification_log.mark_all_as_read`
- `notification_log.trigger_indicator_hide`
- `frappe.client.get_count` / `frappe.client.get_list` on `Notification Log` (feed + unread
  count; always scoped to the recipient via `for_user`, and by the `app` column when `appName`
  is set)
- `frappe.auth.get_logged_user` (to resolve the recipient when `currentUser` isn't passed)
- `frappe.client.get_list` on `User` (to resolve sender avatar images)

Realtime updates listen on the `notification` event.
