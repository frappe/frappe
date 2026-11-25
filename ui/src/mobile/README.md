# Mobile pages

Phone-sized pages any Frappe app can draw: `Search`, `Notifications`, and the parts of a
`Profile` page. They render what they are given. The host fetches the data, passes it in as
props, and routes on the events.

```ts
import { Search, Notifications, Profile, ProfileGroup, ProfileRow } from "@framework/ui/mobile";
```

Desk uses them in `frappe/desk/page/search`, `notifications` and `profile`.

## Search

```vue
<Search v-model:query="query" :results="results" :loading="loading" @select="open" />
```

| Prop          | Type             | Notes                                          |
| ------------- | ---------------- | ---------------------------------------------- |
| `results`     | `SearchResult[]` | `{ label, description?, icon? }`, plus your own keys |
| `loading`     | `boolean`        | Hides the empty state while a search runs      |
| `placeholder` | `string`         | Defaults to "Search"                           |

- `v-model:query` is the text in the input. Debounce and fetch in the host.
- `select(item, event)` fires when a row is chosen.
- Slots: `header` (`{ query }`), `item-prefix`, `item-label`, `item-suffix` (`{ item, index }`),
  `loading`, `empty` (`{ query }`).
- `focus()` is exposed on the component ref.

## Notifications

Takes the same data props as `NotificationPanel`, so one `useNotifications` store feeds both.

```vue
<Notifications
	v-bind="store"
	@select="open"
	@mark-as-read="(n) => store.markAsRead(n.name)"
	@mark-all-as-read="store.markAllAsRead"
	@load-more="store.loadMore"
/>
```

| Prop            | Type                | Notes                                   |
| --------------- | ------------------- | --------------------------------------- |
| `notifications` | `NotificationLog[]` |                                         |
| `unreadCount`   | `number`            | Used by a tab with `count: "unread"`    |
| `hasNextPage`   | `boolean`           | Shows "Load more"                       |
| `loading`       | `boolean`           | Shows the skeleton until rows arrive    |
| `error`         | `unknown`           | Shows the error state when there are no rows |
| `tabs`          | `NotificationTab[]` | Defaults to Unread (`unread`) and Read (`read`) |

- `v-model:activeTab` is the open tab's value. It starts on the first tab.
- Events: `select`, `mark-as-read`, `mark-all-as-read`, `load-more`, `tab-change`. Choosing a
  row emits `select` only, so mark it read there if you want that.
- Slots: `header`, `item-prefix`, `item-label`, `item-suffix` (`{ item, index }`), `loading`,
  `error`, `empty` (`{ activeTab }`).
- A title is HTML and is sanitised before it is rendered.

## Profile

```vue
<Profile>
	<template #header>...</template>
	<ProfileGroup :label="__('Settings')">
		<ProfileRow icon="lucide-globe" :label="__('Time Zone')" :value="zone" @click="edit" />
	</ProfileGroup>
</Profile>
```

- `Profile` is the scrolling frame. `header` is centred above the groups.
- `ProfileGroup` takes a `label` and draws one rounded panel. Its body can hold any element.
- `ProfileRow` is a button: `label`, `value` (muted, on the right), `icon` (a `lucide-*` name or
  a component). Slots `prefix` and `suffix` replace the icon and the chevron. A row draws a
  divider above itself unless it is the first child of its group.

## Styling

Each part carries a `data-slot`: `search`, `search-input`, `search-empty`, `notifications`,
`notifications-header`, `notifications-loading`, `notifications-error`, `notifications-empty`,
`profile`, `profile-header`, `profile-group`, `profile-group-label`, `profile-row`,
`profile-row-prefix`, `profile-row-label`, `profile-row-value`, `profile-row-divider`.

Rows in `Search` and `Notifications` are frappe-ui list rows (`[data-slot=list-row]`). An unread
notification row has `data-unread`.
