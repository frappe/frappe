# ActivityTimeline

A controlled, slot-driven timeline that renders a document's activity feed — emails,
comments, assignment/attachment/workflow logs, and folded version history — as a single
vertical thread. The component only renders; the `useActivityTimeline` composable owns
fetching, caching, realtime updates, and paging older rows.

## The mental model

1. **Presentational.** `<ActivityTimeline>` takes an `activities` array and renders it.
   It never fetches, never subscribes, never persists. Give it rows, it draws the thread.
2. **Composable owns the data layer.** `useActivityTimeline(doctype, docname)` fetches the
   feed, keeps it live over the socket (`doc_subscribe` / `docinfo_update` / `doc_update`),
   caches per `doctype:docname` (and per `visibleTypes` filter), and hands back a
   ready-to-spread props object.
3. **Slots for everything custom.** Any row can be overridden by type, and consumer-defined
   activity types render through `#item-{type}` — so an app can drop its own events into the
   same thread without touching this component.

> The common path is one line of wiring: spread the composable's return into the component.

## Quick start

```vue
<script setup lang="ts">
import {
  ActivityTimeline,
  TimelineContainer,
  useActivityTimeline,
} from "@framework/ui";

const { activities, loading } = useActivityTimeline(
  "HD Ticket",
  route.params.ticketId
);
</script>

<template>
  <TimelineContainer>
    <ActivityTimeline :activities="activities" :loading="loading" />
  </TimelineContainer>
</template>
```

For pagination, bind `paginate` too — see [Pagination](#pagination). `TimelineContainer`
gives the timeline the bounded height its scroller needs — see
[Height and scrolling](#height-and-scrolling).

> The composable lives in the **consuming app**, not in `@framework/ui` — this keeps the
> shared renderer decoupled from where activities come from. `useActivityTimeline` binds its
> args once; remount with a `:key` to switch documents.

## The component

`<ActivityTimeline>` — renders the feed and the "Load more" affordance.

| Property      | Details                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Props**     | `activities: Array<Activity \| CustomActivity>` (required), `loading?: boolean`, `paginate?: Pagination`                                                                                                                                                                                                                                                                                                                         |
| **Loading**   | First-load spinner shows only while `loading` **and** `activities` is empty; cached rows stay visible during revalidation                                                                                                                                                                                                                                                                                                        |
| **Empty**     | Renders a built-in "No activity found" state when `activities` is empty and not loading; replace it via the `#empty` slot                                                                                                                                                                                                                                                                                                        |
| **Scrolling** | The component is its own scroll container (`column-reverse`): give it a bounded height — wrap it in `TimelineContainer`, or `flex-1 min-h-0` by hand — and it opens anchored at the newest row, stays pinned as content grows, and keeps the viewport still when older pages prepend — all natively, no scroll scripting. Unbounded, an ancestor scrolls it like any block and none of that works. DOM order stays chronological |
| **Exposes**   | `scrollToRow(key: string): boolean` — scrolls the row with that key into view and highlights it for two seconds (deep links); a version row folded into a run scrolls to the run; returns `false` if the key isn't rendered. `scrollToLatest()` — jumps to the newest row (no flash); works in both scroll modes, so page-scroll layouts can call it on mount to open at the bottom                                                                                                                     |

### Height and scrolling

The timeline scrolls itself, so something must bound its height — otherwise it grows to
full content height, an ancestor scrolls it, and the bottom-anchored behavior can't work.
`TimelineContainer` is that something: drop it between your page's header and composer
and it fills the leftover space, handing the timeline a real height. Its one requirement:
its parent has a height. In a flex column (`flex h-full flex-col`) it takes the leftover
space between siblings; in any other bounded parent it fills it. Equivalent to putting
`flex-1 min-h-0` on the timeline yourself — use whichever reads better.

It also fades the top and bottom edges so rows don't cut off hard against the header and
composer; pass `:fade="false"` to turn that off.

```vue
<div class="flex h-full flex-col">
  <TicketHeader />
  <TimelineContainer>
    <ActivityTimeline :activities="activities" />
  </TimelineContainer>
  <ReplyComposer />
</div>
```

On a page that scrolls as a document (no bounded height anywhere), the timeline degrades
gracefully — the page scrolls it like any block and it opens at the top; call
`scrollToLatest()` on mount to open at the bottom. Pinning and stable prepends need the
bounded layout above.

### Slots

Every slot receives the row it renders, so overrides stay type-safe.

| Slot           | Payload                 | Use                                                         |
| -------------- | ----------------------- | ----------------------------------------------------------- |
| `#item-{type}` | `{ activity }`          | Replace the body for one activity type (built-in or custom) |
| `#icon-{type}` | `{ activity }`          | Replace the gutter icon/avatar for one type                 |
| `#default`     | `{ item }`              | Replace the body for **every** row (full custom renderer)   |
| `#empty`       | —                       | Replace the built-in "No activity yet" state                |
| `#load_more`   | `{ loading, loadMore }` | Replace the default "Load more" control                     |

```vue
<ActivityTimeline :activities="activities">
  <!-- custom body for a bespoke row type -->
  <template #item-sla_breach="{ activity }">
    <SlaBreachRow :breach="activity.data" />
  </template>
  <!-- custom gutter icon for the same type -->
  <template #icon-sla_breach>
    <LucideTriangleAlert class="size-4 text-ink-red-3" />
  </template>
</ActivityTimeline>
```

## Activity types

Each row is a discriminated union on `type`; the discriminant picks the default renderer and
the `#item-{type}` / `#icon-{type}` slot names.

| `type`           | Renders       | `data` highlights                                     |
| ---------------- | ------------- | ----------------------------------------------------- |
| `email`          | `EmailItem`   | `subject`, `sender`, `content`, `attachments`         |
| `comment`        | `CommentItem` | `content`, `attachments`                              |
| `log`            | `LogItem`     | `subtype` (like / assigned / workflow / …), `text`    |
| `attachment_log` | `LogItem`     | `action` (added / removed), `fileName`, `fileUrl`     |
| `version`        | `VersionItem` | folded field changes (`prefix`, `from`→`to`, `group`) |

Every activity also carries `key` (v-for key + scroll anchor, prefixed by type, e.g.
`comment:42`), an optional `timestamp`, `author`, and `icon`.

### `email` and `comment` `data`

The two rows you most often customize. Each is `{ type, key, timestamp, author, data }`
with a typed `data` payload:

```ts
// email — EmailActivity
{
  type: "email",
  key: "email:123",
  timestamp: "2026-07-01 10:00:00",
  author: { email, fullname, image },
  data: {
    name: string;          // Communication docname
    subject?: string;
    sender: string;
    to?: string;           // comma-joined recipients
    cc?: string;
    bcc?: string;
    content: string;       // HTML body
    deliveryStatus?: string;
    attachments?: { file_url: string; file_name?: string; is_private?: 0 | 1 }[];
  },
}

// comment — CommentActivity
{
  type: "comment",
  key: "comment:42",
  timestamp: "2026-07-01 10:05:00",
  author: { email, fullname, image },
  data: {
    name: string;          // Comment docname
    content: string;       // HTML
    attachments?: { file_url: string; file_name?: string; is_private?: 0 | 1 }[];
  },
}
```

### Built-in item components

`EmailItem` and `CommentItem` are exported so you can reuse the default row and only override
a region. Render one inside its `#item-{type}` slot and fill its region slots (`#actions` is
rendered only when you supply it — neither ships default buttons).

| Component     | Props                                                   | Emits                        | Region slots                                                     |
| ------------- | ------------------------------------------------------- | ---------------------------- | ---------------------------------------------------------------- |
| `EmailItem`   | `{ email }`                                             | —                            | `#header` (`{ email }`), `#actions`, `#footer` (`{ email }`)     |
| `CommentItem` | `{ comment, editable?, editorClass?, uploadFunction? }` | `save(content)`, `discard()` | `#header` (`{ comment }`), `#actions`, `#footer` (`{ comment }`) |

`CommentItem` renders through frappe-ui's `Editor` + `CommentKit` (from
`frappe-ui/editor`). While editing it autofocuses at the end of the text and saves on
Ctrl/⌘-Enter; Discard reverts to the saved content. `editorClass` (default
`"prose-sm max-w-none"`) lands on the editor content, `uploadFunction` (image uploads)
passes through to the editor.

`EmailItem`'s default header is responsive: from `sm` up it's one row (name, status,
time, actions); below that the time moves to its own line under the name, with
To/Cc/Bcc following.

`LogItem` / `VersionItem` are one-liners with no regions — replace the whole row via
`#item-{type}` if you need to change them.

## Custom activities

To render an app-specific event, add a row whose `type` is your own string (typed as
`CustomActivity`) and provide the matching `#item-{type}` slot. Give it a prefixed `key` so
v-for and scroll-to stay stable, and a `timestamp` so it sorts into place. The composable only
returns the document's own activities, so you merge yours in yourself — see
[Example 4: Own activities](#4-own-activities).

## Pagination

The feed is one list over every type, read newest first in pages the server sizes (50).
The first read takes the newest page; each older page is read with the cursor (`before`)
the previous page returned, and its rows are prepended. The list has ended when the server
returns no cursor, or an older page adds no row and returns the cursor it was read with. `paginate` is the same object the composable returns; pass it through and the
component draws the control for you.

| Property             | Details                                                                  |
| -------------------- | ------------------------------------------------------------------------ |
| `hasNextPage`        | `boolean` — whether older rows remain                                    |
| `isFetchingNextPage` | `boolean` — an older page is in flight                                   |
| `fetchNextPage()`    | Reads the next older page and prepends it; concurrent calls share a read |
| `loadMore?`          | Control config — `position` (`"top"` \| `"bottom"`), `label`, `icon`     |

While `isFetchingNextPage` is true the component draws one loading row at the top, the
oldest end. Otherwise, when `hasNextPage` is true, it draws a "Load more" button at the top,
or at the bottom with `position: "bottom"`. A host that loads older rows on scroll calls
`fetchNextPage()` itself. A failed read sets the composable's `error` and leaves
`hasNextPage` as it was, so a loop that pages until it finds a row must also stop on `error`.

Override the button copy by spreading the returned `paginate`:

```vue
<ActivityTimeline
  :activities="activities"
  :paginate="{
    ...paginate,
    loadMore: { label: 'Show previous activity', icon: 'lucide-chevrons-up' },
  }"
/>
```

To replace the button entirely, use the `#load_more` slot — scoped with
`{ loading, loadMore }`:

```vue
<ActivityTimeline :activities="activities" :paginate="paginate">
  <template #load_more="{ loading, loadMore }">
    <Button variant="subtle" :loading="loading" @click="loadMore">Older messages</Button>
  </template>
</ActivityTimeline>
```

## The composable

`useActivityTimeline(doctype, docname, visibleTypes?)` → the data layer.

| Argument        | Details                                                                                                              |
| --------------- | -------------------------------------------------------------------------------------------------------------------- |
| `doctype`       | `string`                                                                                                             |
| `docname`       | `string`                                                                                                             |
| `visibleTypes?` | `VisibleTypes` = `Array<Activity["type"] \| { version: string[] }>` — only these activity types; omit for everything |

**Filtering.** `visibleTypes` is applied **server-side** (it reaches the `activity` read as
`types`): the cursor walks only the rows this view shows, so client-side filtering would
leave pages short and ship rows that are never shown. Each filter has its own store and
cursor, so an Emails view (`["email"]`) never shares a page with the full feed. Realtime-spliced rows pass
through the same filter for feed consistency. An entry may be a type name, or
`{ version: [...fieldnames] }` to narrow version rows to those fields — the allowlist
means _only these fields_, so doc-level version rows (submit/cancel) drop too. Child-table
changes carry the table's fieldname, so listing it keeps its row adds/removes/edits:

```ts
const { activities } = useActivityTimeline("HD Ticket", name, [
  "email",
  "comment",
  { version: ["status", "priority"] },
]);
```

Returns:

| Member       | Details                                                                                                               |
| ------------ | --------------------------------------------------------------------------------------------------------------------- |
| `activities` | `ComputedRef` — deduped, sorted, and grouped rows ready for the component                                             |
| `loading`    | `ComputedRef<boolean>`                                                                                                |
| `reload()`   | Re-read the newest page; older rows already loaded stay when the page reaches them. When more than a page arrived since the last read, the held rows go and paging resumes from the new page's cursor. Coalesced, so N callers in the same moment cost one request. Returns a promise |
| `paginate`   | `Pagination` — reads older pages by cursor; bind it to the component only if you want pagination                       |

`prefetchActivityTimeline(doctype, docname, visibleTypes?)` starts the newest-page read
before any component mounts and resolves once that page is in; a later `useActivityTimeline`
with the same arguments uses it, and its first mount reads nothing more. A store outlives
its components: the twenty most recently used stores with no component mounted are kept,
and an older one is freed. Mounting beside a consumer already mounted on it reads nothing; the first mount
after every consumer left re-reads the newest page, since the socket was closed in between.
`endActivityPrefetch(doctype, docname, visibleTypes?)` says the first paint is over: a first
mount after it re-reads too, since nothing listened between the prefetch and that mount.

With no component mounted, `activityTimelineRows(doctype, docname, visibleTypes?)` returns
the rows a store holds (none if no read began), and `reloadActivityTimeline(...)` re-reads
its newest page, or starts the first read.

**Realtime.** While mounted it subscribes to the doc's socket room and patches the feed
live. Two server events drive it:

| Event            | Carries                     | What happens                               |
| ---------------- | --------------------------- | ------------------------------------------ |
| `docinfo_update` | the whole row (`as_dict()`) | spliced into the feed, no request; an add for a key already in the feed is ignored |
| `doc_update`     | `{doctype, name, modified}` | too thin to splice, so: a coalesced re-read of the newest page |

Comments, likes, assignments, attachments and emails arrive whole via `docinfo_update`
(published by Comment and Communication). Everything else (a status change, an SLA field,
a version row) comes through `doc_update`.

Three things happen for you:

- **One subscription per document.** The socket wiring lives on the shared
  `doctype:docname` store and is reference-counted, so two components on the same document
  share one room, one set of handlers and one refetch.
- **Refetches are coalesced.** One save fires several `doc_update`s (`_comments`,
  `modified`, the field itself); they join a 300ms window and produce one request.
- **Reconnects heal.** A room is server-side state on a socket id and Redis pub/sub buffers
  nothing, so after a drop you are in no room and the gap is lost silently. On `connect`
  after a `disconnect` it rejoins every held room and fires one catch-up refetch. Same on
  mounting onto an already-fetched store, unless a prefetch read it for that mount.

> Reconnect healing only runs if socket.io actually reconnects: check your app's
> `reconnectionAttempts`, since a low value means it gives up after a short outage and
> `connect` never fires.

## Optimistic updates

A send is two round trips (create, then refetch), so the composer looks dead for a moment,
and with the socket down the row may not arrive at all. `addPendingActivity` puts it in the
feed immediately.

```ts
import { addPendingActivity } from "@framework/ui";

const row = addPendingActivity("HD Ticket", ticketId, {
  type: "comment",
  timestamp: dayjs().format("YYYY-MM-DD HH:mm:ss"),
  author: { email: user.email, fullname: user.full_name },
  data: { name: "", content },
});
// clear the composer now; the feed row is the only copy on screen

onSuccess: (res) => {
  const name = typeof res === "string" ? res : res?.message;
  name ? row.resolve(`comment:${name}`) : row.drop();
},
onError: () => {
  row.drop();
  content.value = draft; // put the composer back
},
```

`addPendingActivity(doctype, docname, activity)` takes any `Activity` or `CustomActivity`
minus `key`, and returns `{ resolve(key, timestamp?), drop() }`. The row is keyed
`pending:<uuid>` and shows only in views whose `visibleTypes` include its type.

`resolve` swaps the row to the key and timestamp the server gave it and clears `pending`, so
it needs the create endpoint to return the new document's name. The row keeps the DOM node
it was drawn in: its first key stays on it as `renderKey`, which the component uses as the
v-for key. When the server row arrives (a `docinfo_update` add or a re-read), it takes the
row's place under the same `renderKey`: no flicker, no duplicate, no remount. If the socket
row arrives before the create answers, the pending row is matched on its text, against
rows that arrived after it was added. If
your endpoint returns no name, `drop()` on success and let the refetch bring the row in.

Only call `resolve` on a response that confirms the write: the resolved row stays on screen
until a read brings its server row.

**Rendering.** Pending rows carry `pending: true` and render muted and non-interactive.
Anything keyed by document name (reactions, separately-fetched attachments) has nothing to
key on yet, so read it off the row while pending:

```ts
if (activity.pending)
  return { reactions: [], attachments: activity.data.attachments ?? [] };
```

**Replacing a row in flight.** Hold the handle in module scope and `drop()` the previous one
if a second send can start before the first resolves (a debounced editor, a retry).

## Smart folding

The composable returns the feed deduped by `key` and sorted oldest-first, but
**ungrouped** — the component folds version and assignment runs at render time, over the
rows the consumer actually passes in (after its own filtering and merging). The split of
responsibility is deliberate — the **backend ships each change as structured,
already-translated data** (what kind of change it is + the words), and the **frontend
owns all cross-row merging, before→after layout, and truncation**, because merging is a
cross-row decision that must recompute on every reload.

**Version folding** — consecutive same-author `version` rows ≤15 min apart collapse into
one summary (`VersionItem` renders it as an "N changes over M minutes" session group).
One sentence: _consecutive changes by the same author within 15 minutes fold into one
row._

- **Same field across saves** → net `first.from → last.to`; every hop is kept in `history`
  (revealed by a chevron). **No-op churn** (`H→B→H`) stays visible — the chevron shows
  the round trip.
- **Any visible row in between** (a comment, a call) **splits the fold**, as does a
  **>15 min gap** — the feed never reorders against other rows. Rows the consumer
  filters out before rendering can't split anything.
- Row **identity keys off the first row** (stable as the run grows, so Vue keeps its
  expanded state); the timestamp comes from the last.

**Assignment folding** — a run of consecutive same-author assignment logs nets per
assignee (+1 assigned, −1 removed): anyone who nets to zero (assigned then unassigned
within the run) is **dropped**, and named survivors **merge into one comma-joined row per
direction** (assigned / removed).

| input                                      | output                                                |
| ------------------------------------------ | ----------------------------------------------------- |
| `status H→B→C→H`                           | `changed status H → H` (3 hops under the chevron)     |
| `status H→B→C→D`                           | `changed status H → D` (3 hops under the chevron)     |
| `status B→H`, `priority→Low`, `status H→A` | `+3 changes` → `status B → A` / `set priority to Low` |

The backend decides each change's _kind_ (`format_version_change` → `diff` vs `phrase`)
and applies field-level read permissions (`get_permitted_fields` / `is_field_visible`)
before the frontend folds — see `frappe/desk/form/activity.py`. The `VersionChange`
data shape is in [`types.ts`](./types.ts).

## Examples

### 1. Basic

Built-in rendering, no customization — the composable feeds the component.

```vue
<script setup lang="ts">
import {
  ActivityTimeline,
  TimelineContainer,
  useActivityTimeline,
} from "@framework/ui";

const props = defineProps<{ ticketId: string }>();
const { activities, loading, paginate } = useActivityTimeline(
  "HD Ticket",
  props.ticketId
);
</script>

<template>
  <TimelineContainer>
    <ActivityTimeline
      :activities="activities"
      :loading="loading"
      :paginate="paginate"
    />
  </TimelineContainer>
</template>
```

### 2. Basic + `#actions` slot

The timeline has no emits. Render the built-in `EmailItem` / `CommentItem` inside their
`#item-{type}` slot and wire interactions through the item's `#actions` region — the row is
already in scope from the outer slot, so `#actions` needs no props.

```vue
<script setup lang="ts">
import { ActivityTimeline, EmailItem, CommentItem } from "@framework/ui";
import { Button } from "frappe-ui";
import LucideReply from "~icons/lucide/reply";
// ...composable as above
</script>

<template>
  <ActivityTimeline :activities="activities" :loading="loading">
    <template #item-email="{ activity }">
      <EmailItem :email="activity">
        <template #actions>
          <Button variant="ghost" tooltip="Reply" @click="onReply(activity)">
            <template #icon><LucideReply class="text-ink-gray-7" /></template>
          </Button>
        </template>
      </EmailItem>
    </template>

    <template #item-comment="{ activity }">
      <CommentItem :comment="activity">
        <template #actions>
          <Button variant="ghost" icon="lucide-pencil" @click="onEdit(activity)" />
          <Button variant="ghost" icon="lucide-trash-2" @click="onDelete(activity)" />
        </template>
      </CommentItem>
    </template>
  </ActivityTimeline>
</template>
```

### 3. Basic + custom comment renderer

Replace the comment body entirely with your own component — the default `CommentItem` is not
rendered.

```vue
<template>
  <ActivityTimeline :activities="activities" :loading="loading">
    <template #item-comment="{ activity }">
      <MyComment :comment="activity.data" :author="activity.author" />
    </template>
    <!-- optional: also swap the gutter icon -->
    <template #icon-comment>
      <LucideMessageCircle class="size-4 text-ink-gray-5" />
    </template>
  </ActivityTimeline>
</template>
```

### 4. Own activities

Merge a consumer-defined row into the feed and render it via its `#item-{type}` slot. Re-sort
after merging so it lands in the right spot (the feed is oldest-first).

```vue
<script setup lang="ts">
import { ActivityTimeline, useActivityTimeline } from "@framework/ui";
import type { CustomActivity } from "@framework/ui";
import { computed } from "vue";

const { activities } = useActivityTimeline("HD Ticket", props.ticketId);

const breach: CustomActivity = {
  type: "sla_breach",
  key: "sla_breach:1",
  timestamp: "2026-07-01 14:00:00",
  author: { fullname: "SLA Bot" },
  data: { policy: "Priority-1 Response", minutesLate: 12 },
};

const feed = computed(() =>
  [...activities.value, breach].sort((a, b) =>
    (a.timestamp ?? "").localeCompare(b.timestamp ?? "")
  )
);
</script>

<template>
  <ActivityTimeline :activities="feed">
    <template #item-sla_breach="{ activity }">
      <SlaBreachRow :breach="activity.data" />
    </template>
    <template #icon-sla_breach>
      <LucideTriangleAlert class="size-4 text-ink-red-3" />
    </template>
  </ActivityTimeline>
</template>
```

### 5. Inline comment editing

`CommentItem` accepts `:editable` — when `true` it swaps its body for a `TextEditor` with
built-in Discard / Save buttons (its `#actions` are hidden while editing) and emits
`save(content)` / `discard()`. Track which row is editable yourself, keyed by `activity.key`.

```vue
<script setup lang="ts">
import { ActivityTimeline, CommentItem } from "@framework/ui";
import { Button } from "frappe-ui";
import { ref } from "vue";

const editingKey = ref<string | null>(null);

function onSave(activity, content: string) {
  // persist content...
  editingKey.value = null;
}
</script>

<template>
  <ActivityTimeline :activities="activities" :loading="loading">
    <template #item-comment="{ activity }">
      <CommentItem
        :comment="activity"
        :editable="editingKey === activity.key"
        @save="(content) => onSave(activity, content)"
        @discard="editingKey = null"
      >
        <!-- shown only when NOT editing -->
        <template #actions>
          <Button
            variant="ghost"
            icon="lucide-pencil"
            @click="editingKey = activity.key"
          />
        </template>
      </CommentItem>
    </template>
  </ActivityTimeline>
</template>
```

## Bring your own data layer

The composable is optional. If your activities come from somewhere else — a different
endpoint, a store, static data — build the `Array<Activity | CustomActivity>` yourself and
pass it straight to the component. You lose the built-in caching, realtime, and
paging, but everything about rendering (types, slots, empty/loading states) works the
same. Supply your own `paginate` object if you need "Load more".

## Changed

- `Pagination.isPagedRow`, `loadMore.position: "inline"` and the composable's default
  `loadMore` are gone. The feed is one list under one cursor, so the control sits at the top
  (or the bottom), and a host that loads on scroll calls `fetchNextPage()` itself.
- A resolved pending row stops looking muted when `resolve` is called, before its server
  row arrives.
- `compareActivities(a, b)` is exported: the server's order, the timestamp string and then
  the key, each compared by code unit. Sort merged rows with it so they match the pages.
