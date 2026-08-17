# ActivityTimeline

A controlled, slot-driven timeline that renders a document's activity feed — emails,
comments, assignment/attachment/workflow logs, and folded version history — as a single
vertical thread. The component only renders; the `useActivityTimeline` composable owns
fetching, caching, realtime updates, and email pagination.

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

### Prefetching

`prefetchActivityTimeline(doctype, docname, visibleTypes?)` starts (or reuses) the same
shared fetch without mounting anything, and returns the resource. Call it from a page
shell so a top-level loading gate can wait on `.fetched` — the timeline then mounts with
its data already there, avoiding a second in-panel loading state.

## The component

`<ActivityTimeline>` — renders the feed and the "Load more" affordance.

| Property      | Details                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Props**     | `activities: Array<Activity \| CustomActivity>` (required), `loading?: boolean`, `paginate?: Pagination`                                                                                                                                                                                                                                                                                                                         |
| **Loading**   | First-load spinner shows only while `loading` **and** `activities` is empty; cached rows stay visible during revalidation                                                                                                                                                                                                                                                                                                        |
| **Empty**     | Renders a built-in "No activity found" state when `activities` is empty and not loading; replace it via the `#empty` slot                                                                                                                                                                                                                                                                                                        |
| **Scrolling** | The component is its own scroll container (`column-reverse`): give it a bounded height — wrap it in `TimelineContainer`, or `flex-1 min-h-0` by hand — and it opens anchored at the newest row, stays pinned as content grows, and keeps the viewport still when older pages prepend — all natively, no scroll scripting. Unbounded, an ancestor scrolls it like any block and none of that works. DOM order stays chronological |
| **Exposes**   | `scrollToRow(key: string): boolean` — scrolls the row with that key into view and flashes it (deep links); returns `false` if the key isn't rendered. `scrollToLatest()` — jumps to the newest row (no flash)                                                                                                                                                                                                                    |

### Height and scrolling

The timeline scrolls itself, so something must bound its height — otherwise it grows to
full content height, an ancestor scrolls it, and the bottom-anchored behavior can't work.
`TimelineContainer` is that something: drop it between your page's header and composer
and it fills the leftover space, handing the timeline a real height. Its one requirement:
the page root it sits in is a bounded flex column (`flex h-full flex-col`).

```vue
<div class="flex h-full flex-col">
  <TicketHeader />
  <TimelineContainer>
    <ActivityTimeline :activities="activities" />
  </TimelineContainer>
  <ReplyComposer />
</div>
```

It's equivalent to putting `flex-1 min-h-0` on the timeline yourself — use whichever
reads better. Skip both only when you want an ancestor to own the scroll (and are fine
losing open-at-bottom, pinning, and stable prepends).

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

`LogItem` / `VersionItem` are one-liners with no regions — replace the whole row via
`#item-{type}` if you need to change them.

## Custom activities

To render an app-specific event, add a row whose `type` is your own string (typed as
`CustomActivity`) and provide the matching `#item-{type}` slot. Give it a prefixed `key` so
v-for and scroll-to stay stable, and a `timestamp` so it sorts into place. The composable only
returns the document's own activities, so you merge yours in yourself — see
[Example 4: Own activities](#4-own-activities).

## Pagination

Emails and milestones page in oldest-direction on demand; the remaining sources arrive whole
on the first load. `paginate` is the same object the composable returns; pass it through and
the component wires the "Load more" control for you. One control advances both paged sources.

| Property             | Details                                                                               |
| -------------------- | ------------------------------------------------------------------------------------- |
| `hasNextPage`        | `boolean` — whether older paged rows remain                                           |
| `isFetchingNextPage` | `boolean` — a page is in flight                                                       |
| `fetchNextPage()`    | Load and append the next older page                                                   |
| `isPagedRow?`        | `(activity) => boolean` — rows the next page extends; defaults to email rows          |
| `loadMore?`          | Affordance config — `position` (`"top"` \| `"bottom"` \| `"inline"`), `label`, `icon` |

`position: "inline"` injects a `load_more` row directly above the oldest row `isPagedRow`
matches; `top` / `bottom` render a standalone button. Omit `loadMore` for a default top button.

The control is configured through the `paginate.loadMore` object you pass. The composable
bakes in a default (`{ position: "inline", label: "Show previous activity", icon:
"lucide-chevrons-up" }`); override it by spreading the returned `paginate`:

```vue
<ActivityTimeline
  :activities="activities"
  :paginate="{
    ...paginate,
    loadMore: { ...paginate.loadMore, position: 'bottom' },
  }"
/>
```

To replace the control entirely (at every position it renders), use the `#load_more` slot
— scoped with `{ loading, loadMore }`:

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

**Filtering.** `visibleTypes` is applied **server-side** (it reaches
`get_activity_timeline`): pagination runs over the merged feed, so client-side filtering
would break page math and ship rows that are never shown. Realtime-spliced rows pass
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
| `reload()`   | Refetch the feed                                                                                                      |
| `paginate`   | `Pagination` — "Load more" controller for emails and milestones; bind it to the component only if you want pagination |

**Realtime.** While mounted it subscribes to the doc's socket room and
patches the feed live — new comments/likes/assignments/attachments arrive via
`docinfo_update`, and field changes trigger a reload via `doc_update`. It unsubscribes on
unmount.

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
          <Button variant="ghost" icon="edit-2" @click="onEdit(activity)" />
          <Button variant="ghost" icon="trash-2" @click="onDelete(activity)" />
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
            icon="edit-2"
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
pass it straight to the component. You lose the built-in caching, realtime, and email
pagination, but everything about rendering (types, slots, empty/loading states) works the
same. Supply your own `paginate` object if you need "Load more".
