# ActivityTimeline

A document's activity feed — emails, comments, attachments, log lines and
field-change history — rendered as one chronological timeline.

> **Data and rendering are decoupled.** A composable produces a normalized
> `Activity[]`; a presentational component renders it. The component never knows
> where the activities came from. Normalization lives **server-side**: one
> whitelisted endpoint returns activities already shaped for the renderer.

The package (`@framework/ui`, source at
`apps/frappe/ui/src/components/ActivityTimeline/`) ships two halves, usable
together or independently:

- `useActivityTimeline()` — fetches a Frappe document's activities (data layer)
- `<ActivityTimeline />` — renders any `Activity[]` (render layer)

---

## Quick start

```vue
<script setup lang="ts">
import { ActivityTimeline, useActivityTimeline } from "@framework/ui";

const { activities, loading, error,reload, pagination } =
  useActivityTimeline("HD Ticket", docname);
</script>

<template>
  <ActivityTimeline
    :activities
    :loading
    :error
    :pagination="pagination"
  />
</template>
```

The feed reads **oldest-first**: oldest at the top, newest at the bottom.
`:pagination` is optional — omit it for a static feed (see
[Pagination](#pagination)).

---

## 1. The two layers

```
┌──────────────────────────────────────────────────────────────┐
│ DATA LAYER — useActivityTimeline(doctype, docname)            │
│   • createResource → get_activity_timeline   (default fetcher)│
│   • server returns normalized Activity[] (ascending)         │
│   • dedupe + sort (defensive) + groupConsecutiveVersions     │
│   • pages the email stream via a reactive `pagination`   │
│   • realtime: patches the list in place on docinfo_update    │
│   returns { activities, loading, error, pagination,      │
│             reload }                                          │
└──────────────────────────────────────────────────────────────┘
                       │  Activity[]  (the contract, display order)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ RENDER LAYER — ActivityTimeline.vue (presentational)         │
│   props: { activities, loading?, error?, pagination? }   │
│   NO data fetching. NO doctype/docname. NO emits. Renders.   │
│   EmailItem · CommentItem · LogItem · VersionItem            │
└──────────────────────────────────────────────────────────────┘
```

The two are wired together **at the call site**, not inside the shared
component. The `Activity` discriminated union (`types.ts`) is the only thing
that crosses the boundary. A single backend endpoint
(`frappe.desk.form.activity.get_activity_timeline`) emits that shape directly —
no client-side parsing of raw `docinfo`/`Version` payloads.

---

## 2. The contract — `Activity[]`

A normalized discriminated union (`types.ts`). Every item component renders
*only* from this union — none of them know about `docinfo`, `Version`, or any
backend shape.

```ts
type Activity =
  | EmailActivity         // type: 'email'
  | CommentActivity       // type: 'comment'
  | AttachmentLogActivity // type: 'attachment_log'
  | LogActivity           // type: 'log'   (like / assigned / workflow / info / view …)
  | VersionActivity       // type: 'version' (field-change history; can be grouped)
```

The union stays **closed** so built-in narrowing stays sharp. For
consumer-defined types the package also exports an open escape hatch:

```ts
// same envelope, opaque data — render via the #item-{type} slot
type CustomActivity = BaseActivity<string, unknown>;
```

### Envelope + `data`

Every activity is a **common envelope** the chrome reads, plus a typed `data`
payload only the matching item renderer reads:

```ts
interface BaseActivity<TType extends string, TData> {
  type: TType;                 // discriminant → which item renders
  key: string;                 // REQUIRED — unique; v-for key + scroll target
  timestamp?: string;          // optional — "YYYY-MM-DD HH:mm:ss.ffffff"; sorts correctly as a string
  author?: UserInfo;           // optional — gutter avatar + version grouping (system events omit it)
  icon?: string | Component;   // optional — gutter icon: lucide name or a component
  data: TData;                 // per-type payload
}
```

`author` lives on the envelope so the gutter never special-cases a type, and the
union still narrows: `activity.type === "email"` types `activity.data` as the
email payload. `key` is required on the built-in `Activity` types; on
`CustomActivity` it's optional — the renderer derives a `type:timestamp`/`type:index`
fallback, so an explicit `key` is only needed for reorderable custom rows.
`timestamp` is optional (a row without one sorts to the oldest end).

#### Each type, as a plain object

```js
// email
{ type: "email", key, timestamp, author: { email, fullname, image },
  data: { name, subject, sender, to, cc, bcc, content, deliveryStatus,
          attachments: [{ file_url, file_name?, is_private? }] } }

// comment
{ type: "comment", key, timestamp, author: { email, fullname, image },
  data: { name, content } }

// attachment_log
{ type: "attachment_log", key, timestamp, author,
  data: { name, action: "added" | "removed", fileName, fileUrl?, isPrivate } }

// log
{ type: "log", key, timestamp, author,
  data: { name,
          subtype: "like" | "assigned" | "assignment_completed" | "workflow" | "info" | "view",
          icon, text } }

// version  (data.group present only on a folded run header)
{ type: "version", key, timestamp, author,
  data: { name, text, group?: VersionActivity[] } }
```

The raw → normalized translation is **isolated in the backend**
(`activity.py`); the renderer relies only on the envelope + `data` being
well-formed.

---

## 3. Render layer — `<ActivityTimeline />`

Purely presentational and **controlled**: everything it shows comes from props.
It has **no emits** — wire interactions through the item components' `#actions`
slots (see [Events](#events--reply--edit--delete)).

```ts
interface ActivityTimelineProps {
  activities: Array<Activity | CustomActivity>;
  loading?: boolean;                       // first-load spinner (only when no activities yet)
  error?: string | null;                   // error state instead of the feed
  pagination?: PaginationControls; // scroll-driven paging (optional)
}

interface PaginationControls {
  hasNextPage?: boolean;
  isFetchingNextPage?: boolean;
  fetchNextPage?: () => void | Promise<void>;
}
```

It receives `activities` already in display order (the composable applies it),
dispatches each item to the right item component by `activity.type`, and owns the
**chrome**: gutter dot/avatar, connector line, spacing, ordering, and the
loading / error / empty states. The first-load spinner is gated on
`loading && !activities.length`, so a background refetch over existing rows
leaves them visible (flicker-free).

Because it has no idea where `activities` came from, it works equally with a
doctype, a static fixture, a websocket stream, or a non-Frappe backend.

### Pagination

The feed is fixed **oldest-first**, so "more" always pages **forward in time** —
newer emails appended at the **bottom**. The renderer delegates to
`useLoadMoreOnScroll` (which wraps VueUse's `useInfiniteScroll`): it resolves the
nearest scrollable ancestor at mount and calls `pagination.fetchNextPage()`
once scrolled within ~**400px** of the bottom, gated by
`hasNextPage && !isFetchingNextPage`, re-checking after each page settles. A
spinner shows at the bottom while a page is in flight. There is **no button and
no `@load-more` emit** — the consumer hands over the single `pagination` prop
and the renderer wires the scroll container itself.

`pagination` is **opt-in**, and all three of its fields are optional — omit
the prop (or any field) and the feed is simply static.

---

## 4. Data layer — `useActivityTimeline(doctype, docname)`

The composable that produces activities for a Frappe document. It owns the fetch
policy **and the display order** (fixed **oldest-first**); the renderer owns none
of it.

```ts
const { activities, loading, error, pagination, reload } =
  useActivityTimeline("HD Ticket", "37422");
```

| Field | |
| --- | --- |
| `activities` | `ComputedRef<Activity[]>` — deduped, sorted, grouped, **in display order** |
| `loading` | `ComputedRef<boolean>` — the resource's loading state |
| `error` | `ComputedRef<error \| null>` — the resource's error, or `null` |
| `pagination` | reactive `{ hasNextPage, isFetchingNextPage, fetchNextPage }` — drop straight onto the `:pagination` prop |
| `reload` | `() => void` — refetch the resource |

> **Why `pagination` is `reactive(...)`, not a plain object of refs.** The
> renderer reads `pagination.hasNextPage` expecting a **boolean** (the prop
> type is `boolean`, matching what a bring-your-own consumer passes —
> `comms.hasNextPage`). `reactive()` unwraps the inner refs so the fields read as
> live booleans; a plain object would expose `Ref` wrappers (always truthy),
> breaking the scroll guard and the spinner. The function `fetchNextPage` passes
> through unchanged.

### Paging the email stream

Only the **email/communication** stream is paged (mirrors desk's "Load More
Communications"); comments, logs, views and versions load once as context.

- The backend caps the first page at `EMAIL_PAGE_SIZE` (**20**) **oldest** emails
  and fetches one extra row to set `has_more_emails`.
  `get_activity_timeline` returns `{ activities, has_more_emails }`;
  `get_more_email_activities(doctype, name, start, limit)` returns the next
  (newer) page of already-normalized email `Activity[]` plus its own
  `has_more_emails`.
- Email pagination runs **ascending** via an `order` arg on
  `get_communication_data` (default `desc`, so desk's own timeline is
  unaffected).
- In the composable the first page lives in `resource.data`; each `fetchNextPage`
  appends a newer page into a separate `extraEmails` ref. The `activities`
  computed merges `resource.data.activities + extraEmails` (deduped by `key`),
  then runs the ascending sort + version-grouping — so paged-in emails land at
  the bottom and grouping stays correct. `start` is derived from the count of
  emails already shown, so it self-corrects across realtime adds.
- The server's first-page `has_more_emails` drives `hasNextPage` until the user
  starts paging; after that each `fetchNextPage` response owns it (so a realtime
  reload of page 0 won't reset it).

### Server-side normalization

All normalization the composable used to do — `comment_type` bucketing, HTML
stripping, attachment-link parsing (`fa-lock`, `/app/...`), and label /
permission resolution for version diffs — happens **server-side** in
`activity.py`. The composable receives ready-made `Activity` objects and is a
thin sorter over one default-fetcher resource. Doing the work server-side is
where it belongs: `frappe.get_meta` (field labels) and
`frappe.model.get_permitted_fields` (field-level permission filtering for version
diffs) only exist on the server.

### Realtime — patch in place

The composable keeps the timeline live over a socket. On mount it
`doc_subscribe`s the document room and listens for `docinfo_update`; on dispose
it unsubscribes and removes the listener.

Each event carries `{ doc, key, action }` (`action: "add" | "update" |
"delete"`). The composable runs `normalizeActivity(key, doc)` — a client-side
mirror of the backend normalizers for the `comments`, `like_logs`,
`assignment_logs`, `attachment_logs` and `communications` keys — then **patches
`resource.data.activities` in place**: append on `add`, replace-by-`key` on
`update`, filter-out on `delete`. Unknown keys are ignored.

> **Coverage.** Only emails and comments (plus a few comment-backed logs) emit
> `docinfo_update`. Versions, views, likes and assignments that don't publish
> realtime appear on the next natural reload — matching desk behavior.


### Caching & lifecycle

One `createResource` per `doctype:docname`, kept in a module-level `Map` for the
session. Args are bound at call time — to show a different doc, **remount the
caller with a `:key`**. The resource is cached across remounts; the *socket
subscription* is per-call and torn down on dispose. (Edge case: two timelines for
the **same** doc mounted at once — one unmounting unsubscribes the room for both.
Acceptable today; add ref-counting only if that breaks.)

---

## 5. Customization

All customization is **slot-based** and never touches the chrome (gutter,
connector, spacing, ordering, loading/error/empty, pagination). Two
tiers:

- **Tier 1 — replace a whole row** for a type → `#item-{type}` slot (with a
  **default slot** as the generic catch-all).
- **Tier 2 — tweak a region** of a built-in row → the item's own
  `#header` / `#footer` / `#actions` slots (Comment & Email only).

`{type}` is the activity type: `email`, `comment`, `log`, `attachment_log`,
`version`, or any custom type.

### Tier 1 — `#item-{type}` (every type, free)

`ActivityTimeline` dispatches each row's **content column** through a dynamic
per-type slot, falling back to a default slot, then the built-in component.
First match wins:

```
1. #item-{activity.type}  → use it       (per-type REPLACE, scoped { activity })
2. default slot           → use it       (generic / custom / unknown, scoped { item })
3. (none)                 → built-in     (EmailItem / CommentItem / LogItem / VersionItem)
```

```vue
<!-- content column in ActivityTimeline.vue -->
<slot :name="`item-${activity.type}`" :activity="activity">
  <slot :item="activity">
    <EmailItem   v-if="activity.type === 'email'"     :email="activity" />
    <CommentItem v-else-if="activity.type === 'comment'" :comment="activity" />
    <LogItem     v-else-if="activity.type === 'log' || activity.type === 'attachment_log'" :activity="activity" />
    <VersionItem v-else-if="activity.type === 'version'" :activity="activity" />
  </slot>
</slot>
```

```vue
<ActivityTimeline :activities :loading :error>
  <template #item-comment="{ activity }">
    <MyComment :activity />
  </template>
  <!-- default slot: catch any row not handled by a named #item-{type} -->
  <template #default="{ item }">
    <GenericRow :activity="item" />
  </template>
</ActivityTimeline>
```

### Tier 2 — region slots (Comment & Email only)

The two cards expose **header / footer / actions** regions; each region's default
content is today's markup. The **body is fixed** (no slot — replace the whole row
via `#item-{type}` to change it). The timeline does **not** forward
`#item-{type}-{region}` slots — you reach the regions by **rendering the exported
item inside its `#item-{type}` slot** and filling the item's own slots. The
regions you don't override keep their defaults.

| Item | Props | Emits | Region slots (scoped props) |
| --- | --- | --- | --- |
| **EmailItem** | `{ email }` | — | `#header` (`{ email }`) · `#actions` · `#footer` (`{ email }`) |
| **CommentItem** | `{ comment, editable? }` | `save(content)` · `discard()` | `#header` (`{ comment }`) · `#actions` · `#footer` (`{ comment }`) |

`#actions` is an unscoped slot rendered only when you provide it. Neither card
ships default action buttons — you supply them (e.g. the exported `ReplyIcon` /
`ReplyAllIcon`). `LogItem` / `VersionItem` are one-liners with nothing to
sub-divide → **Tier-1 replace only** (`#item-log`, `#item-attachment_log`,
`#item-version`; `log` and `attachment_log` both render through `LogItem`).

```vue
import { ActivityTimeline, CommentItem } from "@framework/ui";

<ActivityTimeline :activities :loading :error>
  <template #item-comment="{ activity }">
    <CommentItem :comment="activity">
      <!-- override only the header; body & actions keep their defaults -->
      <template #header>
        <MyCommentHeader :author="activity.author" />
      </template>
      <!-- footer is empty by default — add one -->
      <template #footer>
        <div class="mt-1 text-xs text-ink-gray-5">Internal · not visible to customer</div>
      </template>
    </CommentItem>
  </template>
</ActivityTimeline>
```

### Replace the gutter icon — `#icon-{type}` + `icon?`

`#item-{type}` replaces the content column only. The **gutter** is framework-owned
and picks its icon by type. Two channels close this, as a ladder (first match
wins) — symmetric with the content column:

```
1. #icon-{activity.type} slot  → use it                         (per-type gutter REPLACE, scoped { activity })
2. activity.icon present        → component, or lucide string    (data-driven)
3. (neither)                    → per-type default (Avatar / DotIcon / lucide / CommentIcon)
```

```vue
<ActivityTimeline :activities :loading :error>
  <template #icon-comment>
    <FeatherIcon name="message-circle" class="size-4 text-ink-gray-5" />
  </template>
</ActivityTimeline>
```

`icon` on the envelope accepts a **string** (resolved as a lucide name via the
`LUCIDE_ICON_CLASS` literal map) or an **already-imported component** (rendered
via `<component :is>`):

```ts
icon: "circle-check"                      // string → LUCIDE_ICON_CLASS lookup
import AlarmClock from "~icons/lucide/alarm-clock"
icon: AlarmClock                          // component → <component :is>
```

> **Tailwind JIT gotcha.** The string path only renders if the literal
> `lucide-<name>` string is present in the `LUCIDE_ICON_CLASS` map (Tailwind's
> JIT only emits a `lucide-<name>` mask class for literal strings it scans). A
> name not in the map won't render via the string path — pass a component, or use
> the `#icon-{type}` slot (e.g. a `FeatherIcon`).

### Events — reply / edit / delete

`ActivityTimeline` has no emits. Wire events via the item components' `#actions`
slots — `activity` is already in scope from the outer `#item-{type}` slot, so
`#actions` needs no slot props.

```vue
import { ActivityTimeline, EmailItem, CommentItem, ReplyIcon, ReplyAllIcon } from "@framework/ui";

<ActivityTimeline :activities :loading :error>
  <template #item-email="{ activity }">
    <EmailItem :email="activity">
      <template #actions>
        <Button variant="ghost" tooltip="Reply" @click="onReply(activity)">
          <template #icon><ReplyIcon class="text-ink-gray-7" /></template>
        </Button>
        <Button variant="ghost" tooltip="Reply All" @click="onReplyAll(activity)">
          <template #icon><ReplyAllIcon class="text-ink-gray-7" /></template>
        </Button>
      </template>
    </EmailItem>
  </template>

  <template #item-comment="{ activity }">
    <CommentItem
      :comment="activity"
      :editable="editingKey === activity.key"
      @save="(content) => onSave(activity, content)"
      @discard="onDiscard"
    >
      <template #actions>
        <Button variant="ghost" icon="edit-2" @click="onEdit(activity)" />
        <Button variant="ghost" icon="trash-2" @click="onDelete(activity)" />
      </template>
    </CommentItem>
  </template>
</ActivityTimeline>
```

`CommentItem` with `:editable` swaps its body for an inline editor and emits
`save(content)` / `discard()`.

### Custom activity types — type it → merge it → render it

Adding a type the shared package doesn't define needs **no core or composable
support** — the consumer owns the row.

**1. Type it** — the package exports `BaseActivity` + the open `CustomActivity`,
and the prop already accepts it:

```ts
import type { BaseActivity } from "@framework/ui";
type SlaBreach = BaseActivity<"sla_breach", { policy: string; minutesLate: number }>;
```

**2. Merge it** — the composable returns only the doc's own activities. Merge your
row into **your own** computed and re-sort (oldest-first, to match the feed):

```ts
const { activities } = useActivityTimeline("HD Ticket", id);
const slaBreach: CustomActivity = {
  type: "sla_breach", key: "sla_breach:1", timestamp: "2025-10-29 14:00:00",
  author: { fullname: "SLA Bot" }, data: { policy: "Priority-1 Response", minutesLate: 12 },
};
const feed = computed(() => [...activities.value, slaBreach].sort(byTimestamp));
```

There is **no `customActivities` injection** — it's a plain "here's my data, I'll
merge it" computed, which keeps the data layer emitting only the document's
activities.

**3. Render it** — Tier-1 routes it; with no built-in match it renders **nothing
unless `#item-{type}` (or the default slot) is provided**. Set the gutter via
`#icon-{type}` or the envelope `icon`:

```vue
<ActivityTimeline :activities="feed">
  <template #item-sla_breach="{ activity }"> <SlaBreachItem :activity="activity" /> </template>
  <template #icon-sla_breach> <FeatherIcon name="alert-triangle" class="size-4 text-ink-red-3" /> </template>
</ActivityTimeline>
```

Gotchas: `key` must be unique/prefixed (it's the v-for key + sort tiebreak);
`timestamp` is optional but a row without a valid one sorts to the oldest end.

### Other tweak channels

- **`class` passthrough** — items use `inheritAttrs: false` +
  `:class="$attrs.class"` (frappe-ui idiom). There's no `twMerge`/`cn()` in this
  codebase, so it's array-append — override with non-conflicting / specific
  utilities, or use a sub-slot instead of fighting classes.

---

## 6. Wiring the two together (the call site)

The shared package exports the renderer and the composable; the consuming app
joins them. Helpdesk uses a thin app-level wrapper so the doctype binding + `:key`
remount live in the app, not in `@framework/ui`:

```vue
<!-- helpdesk/desk/src/pages/DocActivityTimeline.vue -->
<template>
  <ActivityTimeline
    :activities="activities"
    :loading="loading"
    :error="error"
    :pagination="pagination"
  />
</template>

<script setup lang="ts">
import { ActivityTimeline, useActivityTimeline } from "@framework/ui";
const props = defineProps<{ doctype: string; docname: string }>();
const { activities, loading, error, pagination } =
  useActivityTimeline(props.doctype, props.docname);
</script>
```

```vue
<!-- caller — remount per doc; useActivityTimeline binds its args once -->
<DocActivityTimeline :key="`${doctype}:${docname}`" :doctype :docname />
```

`reload` lives on the composable at the call site (not exposed by the component).

---

## 7. Backend — `frappe/desk/form/`

`activity.py` (whitelisted endpoints + normalizers):

- `get_activity_timeline(doctype, name)` → `{ activities, has_more_emails }` —
  merges creation, the first page of emails, comments/logs, views and versions,
  sorts ascending, returns the normalized `Activity[]`.
- `get_more_email_activities(doctype, name, start, limit=EMAIL_PAGE_SIZE)` →
  `{ activities, has_more_emails }` — the next (newer) email page, normalized.
- `EMAIL_PAGE_SIZE = 20` — page size of the email stream (the only paged source).
  `get_email_activities` over-fetches `limit + 1` rows ascending, sets
  `has_more = len > limit`, then trims — that one extra row is how
  `has_more_emails` (→ frontend `hasNextPage`) is computed.

`load.py` (data layer for communications) gained an `order` arg threaded through
`_get_communications` → `get_communication_data`, defaulting to `"desc"` so every
existing desk caller is untouched. activity.py passes `order="asc"` to page emails
oldest-first. The direction is whitelisted to a literal (`"ASC"`/`"DESC"`) before
being interpolated into the `ORDER BY` clauses — it is never a bound param, so the
whitelist is the injection guard.

---

## 8. File layout

```
# shared package — apps/frappe/ui/src/components/ActivityTimeline/
ActivityTimeline.vue     presentational renderer (props in, slots out)
useActivityTimeline.ts   data layer: fetch + dedupe/sort/group + paging + realtime → Activity[]
useLoadMoreOnScroll.ts   scroll-detection composable (wraps VueUse useInfiniteScroll)
types.ts                 Activity union (the contract) + ActivityTimelineProps + PaginationControls
EmailItem.vue · CommentItem.vue · LogItem.vue · VersionItem.vue   item renderers
EmailContent.vue · AttachmentItem.vue · PreviewDialog.vue          render helpers
icons.ts · utils.ts                                                shared bits
index.ts                 public exports (components, composables, Activity* types)

# backend — apps/frappe/frappe/desk/form/
activity.py              whitelisted get_activity_timeline / get_more_email_activities + normalizers
load.py                  _get_communications / get_communication_data (+ order arg)
```

---

## 9. Design rationale

- **Single contract.** The `Activity` union is the only thing crossing the
  data↔render boundary.
- **Renderer is pure.** Works with a doctype today, or a static fixture / socket /
  non-Frappe backend tomorrow, with zero changes to the component.
- **Data policy is swappable.** Want two docs merged, or doc + injected synthetic
  events? Produce the same shape and feed the same renderer (the playground does
  exactly this for a custom `sla_breach` row).
- **One endpoint.** The data layer used to stitch two calls (`get_docinfo` +
  `get_version_timeline`) and normalize client-side. It's now a single whitelisted
  endpoint returning the already-normalized, ascending `Activity[]` in one
  round-trip — field labels and field-level permission filtering only exist
  server-side, and HTML stripping / `comment_type` bucketing is cheaper and safer
  there.
- **Customization-as-data carries data, not behavior.** The slot ladder
  (per-type `#item`/`#icon` → default slot → built-in) is what Vuetify, Quasar,
  Headless UI and frappe-ui all converge on. Since item slots hand back
  `{ activity }` (data), the ecosystem's behavior-forwarding patterns
  (`asChild`/`as="template"`, PrimeVue `pt` passthrough, render-fn props) add no
  value here — deliberately skipped.

### Considered but not shipped

- `items` component-map prop, and a generic `#item` named slot — replaced by the
  default slot exposing `{ item }`.
- `customActivities` injection into the composable — replaced by consumer-side
  merge.
- An `order` prop / arg — removed; the feed is fixed oldest-first and the email
  stream pages forward via pagination.
- `pin`/row pinning; `RenderableContent` (`{ is, props }`) content form; granular
  email sub-slots (`#recipients`/`#content`/`#attachments`) — replaced by the
  `#header`/`#footer`/`#actions` regions.
- A generic `usePagination` composable — explored, reverted; the email-paging
  state machine stays inline in `useActivityTimeline`.

---

## 10. Playground

The living reference is **`/helpdesk/new`**
(`apps/helpdesk/desk/src/pages/New.vue`, "Activity Timeline — customization
playground"): a doctype + document picker, a scenario toggle, and a "View
Consumer API" dialog showing each scenario's snippet. Harness components live
under `apps/helpdesk/desk/src/pages/activity-playground/`.

| Scenario | Demonstrates |
| --- | --- |
| **basic** | built-in rendering, pagination wired (single `pagination` prop) |
| **replace** | override `#item-comment` with a custom component |
| **icon** | override only the gutter via `#icon-comment`; content stays built-in |
| **regions** | render `CommentItem` inside `#item-comment` and override its `#header` + `#footer` |
| **actions** | wire reply / edit / delete via the items' `#actions` slots |
| **custom** | merge a consumer-defined `sla_breach` row into a computed, re-sort, render via `#item-sla_breach` + `#icon-sla_breach` |

---

## 11. Public exports (`index.ts`)

```ts
export { default as ActivityTimeline } from "./ActivityTimeline.vue";
export { default as EmailItem }   from "./EmailItem.vue";
export { default as CommentItem } from "./CommentItem.vue";
export { default as LogItem }     from "./LogItem.vue";
export { default as VersionItem } from "./VersionItem.vue";
export { useActivityTimeline } from "./useActivityTimeline";
export { ReplyIcon, ReplyAllIcon } from "./icons";
export type {
  Activity, ActivityTimelineProps, AttachmentLogActivity, LogActivity,
  BaseActivity, CommentActivity, CustomActivity, EmailActivity, EmailAttachment,
  PaginationControls, UserInfo, VersionActivity,
} from "./types";
```
