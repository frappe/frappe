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

const { activities, loading, error, reload, paginate } =
  useActivityTimeline("HD Ticket", docname, /* paginate */ true);
</script>

<template>
  <ActivityTimeline
    :activities
    :loading
    :error
    :paginate
  />
</template>
```

The feed reads **oldest-first**: oldest at the top, newest at the bottom.
Comments, logs, views and version history load **in full** on the first call;
**emails are paged** newest-first (a page is `EMAIL_PAGE_SIZE = 20`). Pass
`paginate: true` to give users a **"Load More Emails"** control that pulls in the
next older page — without it, only the newest page of emails is reachable.

---

## 1. The two layers

```
┌──────────────────────────────────────────────────────────────┐
│ DATA LAYER — useActivityTimeline(doctype, docname, paginate?) │
│   • createResource → get_activity_timeline   (default fetcher)│
│   • server returns normalized Activity[] (ascending)         │
│   • dedupe + sort (defensive) + groupVersionActivities       │
│   • paginate=true → returns a `paginate` controller + injects │
│        a `load_more` row above the oldest email              │
│   • realtime: patches the list in place on docinfo_update    │
│   returns { activities, loading, error, reload, paginate? }  │
└──────────────────────────────────────────────────────────────┘
                       │  Activity[]  (the contract, display order)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ RENDER LAYER — ActivityTimeline.vue (presentational)         │
│   props: { activities, loading?, error?, paginate? }         │
│   NO data fetching. NO doctype/docname. NO emits. Renders.   │
│   EmailItem · CommentItem · LogItem · VersionItem            │
│   owns the Load More button + scroll-anchoring               │
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
  | LogActivity           // type: 'log'   (like / assigned / workflow / info / view / created …)
  | VersionActivity       // type: 'version' (field-change history; can be grouped)
```

The union stays **closed** so built-in narrowing stays sharp. For
consumer-defined types the package also exports an open escape hatch:

```ts
// same envelope, opaque data — render via the #item-{type} slot
type CustomActivity = Omit<BaseActivity<string, unknown>, "key"> & { key?: string };
```

### Envelope + `data`

Every activity is a **common envelope** the chrome reads, plus a typed `data`
payload only the matching item renderer reads:

```ts
interface BaseActivity<TType extends string, TData> {
  type: TType;                 // discriminant → which item renders
  key: string;                 // REQUIRED on built-ins — unique; v-for key + scroll target
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

// log  (data.group present when consecutive same-author log rows are folded)
{ type: "log", key, timestamp, author,
  data: { name,
          subtype: "like" | "assigned" | "assignment_completed" | "workflow" | "info" | "view" | "created",
          icon, text, assignee?, group?: LogActivity[] } }
// data.assignee (optional) is the assignment target the backend resolves; the row
// bolds the actor + assignee without parsing the message text

// version  (data.group present on a folded multi-field group header)
// each change is a VersionChange, a discriminated union on `type`:
//   diff   → { name, fieldname?, type: "diff", prefix, from?, to, history? }  (from absent ⇒ set-from-blank)
//   phrase → { name, fieldname?, type: "phrase", text }                    (fieldname null ⇒ doc-level)
{ type: "version", key, timestamp, author,
  data: { ...VersionChange, group?: VersionChange[] } }
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
  paginate?: {                             // when present, enables the "Load More" control
    hasNextPage: boolean;
    isFetchingNextPage: boolean;
    fetchNextPage: () => void;
    position?: "top" | "bottom";           // standalone-button placement; default "top"
  };
}
```

It receives `activities` already in display order (the composable applies it),
dispatches each item to the right item component by `activity.type`, and owns the
**chrome**: gutter dot/avatar, connector line, spacing, ordering, the
loading / error / empty states, **and the Load More button + scroll-anchoring**.
The first-load spinner is gated on `loading && !activities.length`, so a
background refetch over existing rows leaves them visible (flicker-free).

Because it has no idea where `activities` came from, it works equally with a
doctype, a static fixture, a websocket stream, or a non-Frappe backend. The
`paginate` controller is just the shape above — `useActivityTimeline` returns one,
but any source can supply it.

### Load More — button placement & scroll behavior

The feed is oldest-first, so paging pulls **older** emails in **above** the
current oldest one. The component renders the affordance two ways:

```
1. activities contains a row with type: "load_more"   → render it IN-FEED
     (connector line passes through, no gutter icon; consumer owns its position;
      the standalone button is suppressed)
2. otherwise, paginate.hasNextPage is true            → render a STANDALONE button
     at paginate.position ("top" default, or "bottom")
```

When `useActivityTimeline(…, true)` is used, it injects a `load_more` row above
the oldest email for you (case 1). To instead get a standalone button you fully
control, omit that row and bind a bare `paginate` controller with a `position`.

Clicking the button calls `paginate.fetchNextPage()`. Before the older rows patch
in, the component **anchors** a visible row and restores its offset afterward, so
the viewport doesn't jump. On first render (with `paginate`) it scrolls once to
the bottom (newest).

The button itself is an internal `LoadMoreButton` (rendered in whichever of the
three positions is active). Override it for **all** positions at once via the
`#load_more` slot — scoped with `{ loading, loadMore }`:

```vue
<ActivityTimeline :activities :loading :error :paginate>
  <!-- replace the default control everywhere it appears -->
  <template #load_more="{ loading, loadMore }">
    <Button variant="subtle" :loading @click="loadMore">Older messages</Button>
  </template>
</ActivityTimeline>
```

Providing nothing keeps the default "Load more" button.

---

## 4. Data layer — `useActivityTimeline(doctype, docname, paginate?)`

The composable that produces activities for a Frappe document. It owns the fetch
policy **and the display order** (fixed **oldest-first**); the renderer owns none
of it.

```ts
const { activities, loading, error, reload, paginate } =
  useActivityTimeline("HD Ticket", "37422", true);
```

| Field | |
| --- | --- |
| `activities` | `ComputedRef<Activity[]>` — deduped, sorted, grouped, **in display order** (with a `load_more` row injected when paging) |
| `loading` | `ComputedRef<boolean>` — the resource's loading state |
| `error` | `ComputedRef<error \| null>` — the resource's error, or `null` |
| `reload` | `() => void` — refetch the resource |
| `paginate` | the controller (`{ hasNextPage, isFetchingNextPage, fetchNextPage }`) — **only when the 3rd arg is `true`**, else `undefined` |

### Email paging (opt-in)

The third positional arg, `paginate?: boolean`, is the only flag:

- **`paginate` omitted / false** — `activities` is the deduped/sorted/grouped feed
  as-is. The first call already returns only the **newest page** of emails
  (`EMAIL_PAGE_SIZE = 20`), so older emails are simply not shown and there's no
  affordance to fetch them. Everything else (comments, logs, views, versions)
  loads in full.
- **`paginate: true`** — the composable returns a `paginate` controller and
  injects a `load_more` row above the oldest email. `fetchNextPage()` calls
  `get_more_email_activities(doctype, name, start = emailsLoaded)`, appends the
  next older page to `resource.data`, and the `activities` computed re-sorts.
  `hasNextPage` mirrors the server's `has_more_emails` flag. The "older emails
  remain" flag is held in a module-level `Map` keyed by `doctype:docname`, so it
  survives cached remounts.

### Server-side normalization

All normalization the composable used to do — `comment_type` bucketing, HTML
stripping, attachment-link parsing (`fa-lock`, `/app/...`), and label /
permission resolution for version diffs — happens **server-side** in
`activity.py`. The composable receives ready-made `Activity` objects and is a
thin sorter + grouper over one default-fetcher resource (plus a second resource
for the older-email pages). Doing the work server-side is where it belongs:
`frappe.get_meta` (field labels) and `frappe.model.get_permitted_fields`
(field-level permission filtering for version diffs) only exist on the server.

### Version grouping (nested changes)

`groupVersionActivities` runs client-side after the sort: it folds a run of
**consecutive same-author `version` rows** into one summary row whose `data.group`
holds the individual `VersionChange`s. Per field it advances the net `to` (keeping
the first `from`) and records each step in `history`; fields that churn back to
their starting value drop out as net no-ops. `VersionItem` renders the summary as
an expandable **"Show/Hide +N changes"** row, and a single diff with multiple
history entries gets a chevron that reveals its `history`. `LogActivity` carries
the same optional `group`, and `LogItem` renders the identical collapsible UI when
one is present.

### Realtime — patch in place

The composable keeps the timeline live over a socket. On mount it
`doc_subscribe`s the document room and listens for `docinfo_update`; on dispose
it unsubscribes and removes the listener.

Each event carries `{ doc, key, action }` (`action: "add" | "update" |
"delete"`). The composable runs `normalizeActivity(key, doc)` — a client-side
mirror of the backend normalizers for the `comments`, `like_logs`,
`assignment_logs`, `attachment_logs` and `communications` keys — then **patches
`resource.data` in place**: append on `add`, replace-by-`key` on `update`,
filter-out on `delete`. Unknown keys are ignored. (The socket payload has no
avatar, so the author is resolved from an already-loaded row with the same email,
falling back to a name-only `UserInfo`.)

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
connector, spacing, ordering, loading/error/empty, Load More). Two tiers:

- **Tier 1 — replace a whole row** for a type → `#item-{type}` slot (with a
  **default slot** as the generic catch-all).
- **Tier 2 — tweak a region** of a built-in row → the item's own
  `#header` / `#footer` / `#actions` slots (Comment & Email only).

`{type}` is the activity type: `email`, `comment`, `log`, `attachment_log`,
`version`, or any custom type. The slots are **typed**: `defineSlots` maps each
built-in `#item-{type}` / `#icon-{type}` to its narrowed activity, and keeps the
open `#item-${string}` / `#icon-${string}` (plus `default`) for custom types.

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

> The framework-owned `load_more` row is rendered by the component itself (a
> `LoadMoreButton`), **not** through `#item-load_more` — so the slot ladder never
> sees it. Override the button via the dedicated `#load_more` slot, and control
> its placement via `paginate.position` — see
> [Load More](#load-more--button-placement--scroll-behavior).

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
ships default action buttons — you supply them (e.g. your own lucide icons via
`~icons/lucide/reply`). `LogItem` / `VersionItem` are one-liners with nothing to
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
import { ActivityTimeline, EmailItem, CommentItem } from "@framework/ui";
import LucideReply from "~icons/lucide/reply";
import LucideReplyAll from "~icons/lucide/reply-all";

<ActivityTimeline :activities :loading :error>
  <template #item-email="{ activity }">
    <EmailItem :email="activity">
      <template #actions>
        <Button variant="ghost" tooltip="Reply" @click="onReply(activity)">
          <template #icon><LucideReply class="text-ink-gray-7" /></template>
        </Button>
        <Button variant="ghost" tooltip="Reply All" @click="onReplyAll(activity)">
          <template #icon><LucideReplyAll class="text-ink-gray-7" /></template>
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

Gotchas: `key` is optional on `CustomActivity` but must be unique/prefixed when
present (it's the v-for key + sort tiebreak); omitting it falls back to
`type:timestamp` / `type:index`, fine for static rows but not reorderable ones.
`timestamp` is optional — a row without a valid one sorts to the oldest end.

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
    :paginate="paginate"
  />
</template>

<script setup lang="ts">
import { ActivityTimeline, useActivityTimeline } from "@framework/ui";
const props = defineProps<{ doctype: string; docname: string }>();
const { activities, loading, error, paginate } =
  useActivityTimeline(props.doctype, props.docname, true);
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
  merges creation, the **newest page of emails**, comments/logs, views and
  versions, sorts ascending, and returns the normalized `Activity[]` plus a
  `has_more_emails` flag in one call.
- `get_more_email_activities(doctype, name, start)` →
  `{ activities, has_more_emails }` — the next older page of emails only (sorted
  ascending), for the composable to append on Load More.
- `EMAIL_PAGE_SIZE = 20` — non-email sources load in full; emails page
  newest-first. `get_email_activities` fetches `EMAIL_PAGE_SIZE + 1` (DESC) and
  uses the extra oldest row as a "more exist" sentinel before slicing it off.

`load.py` (`_get_communications` / `get_communication_data`) is queried
newest-first with `start` / `limit` so each page is a window over the
communications, paged by the count of emails already loaded.

---

## 8. File layout

```
# shared package — apps/frappe/ui/src/components/ActivityTimeline/
ActivityTimeline.vue     presentational renderer (props in, slots out) + Load More + scroll-anchor
GutterIcon.vue           per-type gutter glyph (avatar+badge / dot / lucide); the default of #icon-{type}
LoadMoreButton.vue       default "Load more" control (override via #load_more)
useActivityTimeline.ts   data layer: fetch + dedupe/sort/group + email paging + realtime → Activity[]
useTimelineScroll.ts     nearest scrollable ancestor + Load More anchor-restore + open-at-bottom-once
types.ts                 Activity union (the contract) + ActivityTimelineProps + paginate shape
EmailItem.vue · CommentItem.vue · LogItem.vue · VersionItem.vue   item renderers (LogItem folds the log text; VersionItem folds the per-change + history renderers)
EmailContent.vue         sandboxed email iframe
Attachment.vue           attachment chip + inline image/text preview dialog
icons.ts · utils.ts                                                shared bits (icons; dates, truncate, splitBold, recipients, iframe helpers)
index.ts                 public exports (components, composables, Activity* types)

# backend — apps/frappe/frappe/desk/form/
activity.py              whitelisted get_activity_timeline + get_more_email_activities + normalizers
load.py                  _get_communications / get_communication_data (paged emails)
```

---

## 9. Design rationale

- **Single contract.** The `Activity` union is the only thing crossing the
  data↔render boundary.
- **Renderer is pure.** Works with a doctype today, or a static fixture / socket /
  non-Frappe backend tomorrow, with zero changes to the component. Even paging is
  just a `paginate` shape — the renderer doesn't fetch.
- **Data policy is swappable.** Want two docs merged, or doc + injected synthetic
  events? Produce the same shape and feed the same renderer (the playground does
  exactly this for a custom `sla_breach` row).
- **One endpoint.** The data layer used to stitch two calls (`get_docinfo` +
  `get_version_timeline`) and normalize client-side. It's now whitelisted endpoints
  returning the already-normalized, ascending `Activity[]` — field labels and
  field-level permission filtering only exist server-side, and HTML stripping /
  `comment_type` bucketing is cheaper and safer there.
- **Emails page, the rest doesn't.** Comments/logs/views/versions are bounded and
  load in full; email threads can be long, so they page newest-first (20 at a
  time). Paging is **opt-in** — pass `paginate: true` only where older emails need
  to be reachable.
- **Load More, not infinite scroll.** An explicit "Load More Emails" button is
  predictable and avoids scroll-jank: the component anchors a visible row and
  restores its offset after older rows patch in, so the viewport never jumps.
  Placement is configurable (`position: "top" | "bottom"`), and a consumer can
  inject their own in-feed `load_more` row to own the position entirely.
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
- An `order` prop / arg — removed; the feed is fixed oldest-first.
- `pin`/row pinning; `RenderableContent` (`{ is, props }`) content form; granular
  email sub-slots (`#recipients`/`#content`/`#attachments`) — replaced by the
  `#header`/`#footer`/`#actions` regions.
- **Infinite-scroll** email paging — built, then dropped in favor of the explicit
  Load More button (no scroll-jank, predictable, placement-configurable).

---

## 10. Playground

The living reference is **`/helpdesk/new`**
(`apps/helpdesk/desk/src/pages/New.vue`, "Activity Timeline — customization
playground"): a doctype + document picker, a scenario toggle, and a "View
Consumer API" dialog showing each scenario's snippet. Harness components live
under `apps/helpdesk/desk/src/pages/activity-playground/`.

| Scenario | Demonstrates |
| --- | --- |
| **basic** | built-in rendering — `:activities :loading :error` only; newest email page + everything else, oldest-first, no Load More |
| **pagination** | opt into email paging (`useActivityTimeline(…, true)`) and bind `:paginate`; the component shows the "Load More Emails" control |
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
export type {
  Activity, ActivityTimelineProps, AttachmentLogActivity, LogActivity,
  BaseActivity, CommentActivity, CustomActivity, EmailActivity, EmailAttachment,
  UserInfo, VersionActivity, VersionChange,
} from "./types";
```
