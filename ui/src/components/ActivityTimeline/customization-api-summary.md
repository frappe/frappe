# ActivityTimeline — Customization API (shipped)

> The implemented surface. For research/rationale see `customization-api.md`;
> for the data contract see `architecture.md`. Status: **implemented.** The live
> reference is the playground at `/helpdesk/new` (see "Try it" below).

Customization splits into two tiers and never touches the **chrome** (gutter
dot/avatar, connector line, spacing, ordering, loading/error/empty):

- **Tier 1 — replace a whole row** for a type → timeline-level `#item-{type}` slots
  (with a default slot as the generic catch-all).
- **Tier 2 — tweak a region** of a built-in row → `#item-{type}-{header,body,footer}`
  (email & comment only).

---

## Tier 1 — `#item-{type}` (all types, free)

`ActivityTimeline` dispatches each row's **content column** through a dynamic
per-type slot, falling back to a **default slot**, then the built-in component.
Resolution order (first match wins):

```
1. #item-{activity.type} slot  → use it       (per-type REPLACE, scoped { activity })
2. default slot                 → use it       (generic REPLACE / custom / unknown, scoped { item })
3. (none)                       → built-in     (EmailItem / CommentItem / AuditItem / VersionItem)
```

```vue
<!-- content column in ActivityTimeline.vue -->
<slot :name="`item-${activity.type}`" :activity="activity">
  <!-- default slot: full per-row override, exposes the row as { item } -->
  <slot :item="activity">
    <EmailItem    v-if="activity.type === 'email'"   :email="activity" />
    <CommentItem  v-else-if="activity.type === 'comment'" :comment="activity" />
    <AuditItem    v-else-if="activity.type === 'audit' || activity.type === 'attachment_log'" :activity="activity" />
    <VersionItem  v-else-if="activity.type === 'version'" :activity="activity" />
  </slot>
</slot>
```

- Slots that exist: `#item-email`, `#item-comment`, `#item-audit`,
  `#item-attachment_log`, `#item-version`, `#item-{anyCustomType}`, and the
  unnamed **default slot**.
- Per-type slots are scoped `{ activity }`; the default slot is scoped `{ item }`.
- Gutter has the symmetric per-type slot too: `#icon-{type}` (scoped `{ activity }`) —
  see "Gutter for custom types" below.
- Because the per-type name is dynamic, **every type — built-in or custom — gets
  a full-replace slot for free**; the default slot catches anything without a
  matching per-type slot.

```vue
<ActivityTimeline :activities="activities">
  <template #item-comment="{ activity }"> <MyComment :comment="activity" /> </template>
  <!-- default slot: catch any row not handled by a named #item-{type} -->
  <template #default="{ item }"> <GenericRow :activity="item" /> </template>
</ActivityTimeline>
```

---

## Tier 2 — region sub-slots (Comment & Email only)

The two multi-region cards expose **header / body / footer** regions; each
region's default content is today's markup. They're surfaced **at the timeline**
as `#item-{type}-{region}`, and forwarded to the built-in item **only when you
provide them** — so the regions you don't override keep their default markup.

| Item | Region slots (at the timeline) | Scoped props |
| --- | --- | --- |
| **CommentItem** | `#item-comment-header` · `#item-comment-body` · `#item-comment-footer` | `{ comment }` (+ `activity`) |
| **EmailItem** | `#item-email-header` · `#item-email-body` · `#item-email-footer` | `{ email }` (+ `activity`) |

```vue
<ActivityTimeline :activities="activities">
  <!-- override only the comment header; body & footer keep their defaults -->
  <template #item-comment-header="{ comment }">
    <MyCommentHeader :author="comment.author" />
  </template>
  <!-- footer is empty by default — add one -->
  <template #item-comment-footer="{ comment }">
    <ReactionBar :id="comment.data.name" />
  </template>
</ActivityTimeline>
```

**Audit / Attachment_log / Version → Tier-1 only.** They're one-liners with
nothing meaningful to sub-divide; customize them by replacing the whole row via
`#item-audit` / `#item-attachment_log` / `#item-version`. (`audit` and
`attachment_log` both render through `AuditItem`.)

You can also re-render the exported built-in item inside a Tier-1 slot and fill
its region slots directly:

```vue
<template #item-comment="{ activity }">
  <CommentItem :comment="activity">
    <template #footer="{ comment }"> <ReactionBar :id="comment.data.name" /> </template>
  </CommentItem>
</template>
```

---

## Custom activity types

Adding a type the shared package doesn't define = **type it → merge it → render it.**
No core or composable support is required — the consumer owns the row.

**1. Type it** — the package exports `BaseActivity` + the open `CustomActivity`,
and the prop already accepts it:

```ts
// @framework/ui types.ts
export type CustomActivity = BaseActivity<string, unknown>;
// ActivityTimeline prop:
activities: Array<Activity | CustomActivity>;
```
```ts
// consumer — define your own typed activity
import type { BaseActivity } from "@framework/ui";
type SlaBreach = BaseActivity<"sla_breach", { policy: string; minutesLate: number }>;
```
Built-in `Activity` union stays closed → built-in narrowing stays sharp.

**2. Merge it** — the composable returns only the doc's own activities. To add a
custom row, merge it into **your own** computed, then re-sort (and re-apply order):

```ts
const { activities } = useActivityTimeline("HD Ticket", id, "asc");
const slaBreach: CustomActivity = {
  type: "sla_breach", key: "sla_breach:1", timestamp: "2025-10-29 14:00:00",
  author: { fullname: "SLA Bot" }, data: { policy: "Priority-1 Response", minutesLate: 12 },
};
const feed = computed(() => [...activities.value, slaBreach].sort(byTimestamp));
```

There is **no `customActivities` injection** into the composable — it's a plain
"here's my data, I'll merge it" computed, which keeps the data layer emitting
only the document's activities.

**3. Render it** — Tier-1 dynamic slot routes it; with no built-in match it
renders **nothing unless `#item-{type}` (or the default slot) is provided**:

```vue
<ActivityTimeline :activities="feed">
  <template #item-sla_breach="{ activity }"> <SlaBreachItem :activity="activity" /> </template>
  <template #icon-sla_breach> <FeatherIcon name="alert-triangle" class="size-4 text-ink-red-3" /> </template>
</ActivityTimeline>
```

Gotchas: `key` must be unique/prefixed (it's the v-for key + sort tiebreak);
`timestamp` is optional but a row without a valid one sorts to the oldest end.
Set `icon` on the envelope or use `#icon-{type}` for the gutter dot (see below) —
without either, a custom row falls to the per-type default.

---

## Gutter for custom types — `#icon-{type}` slot + `icon?` envelope

`#item-{type}` replaces the **content column** only. The **gutter** (dot/avatar +
connector) is framework-owned and picks its icon by type. Two channels close
this, as a ladder (first match wins) — symmetric with the content column:

```
1. #icon-{activity.type}  slot present  → use it           (per-type gutter REPLACE, template)
2. activity.icon          present        → component or lucide string   (data-driven)
3. (neither)                             → per-type default (Avatar / DotIcon / lucide / CommentIcon)
```

### `#icon-{type}` slot (template channel, symmetric with `#item-{type}`)

A dynamic per-type slot in the **gutter column**, scoped `{ activity }`. Full
markup control (badge, stacked avatar, animated dot):

```vue
<ActivityTimeline :activities="activities">
  <template #icon-sla_breach="{ activity }"> <MyGutterDot :activity="activity" /> </template>
</ActivityTimeline>
```

### `icon?` on the envelope (data channel, no markup)

```ts
// types.ts — the full envelope (all additions optional → built-ins/callers unchanged)
interface BaseActivity<TType extends string, TData> {
  type: TType;
  key: string;                 // required
  timestamp?: string;          // optional — a row without one sorts to the oldest end
  author?: UserInfo;           // optional — system/custom events may have none
  icon?: string | Component;   // gutter icon: lucide name (string) or a component
  data: TData;
}
```

`icon` accepts **a string or an already-imported component**:
- **string** → resolved as a lucide name via the `LUCIDE_ICON_CLASS` literal map
  (same convention as `AuditActivity.data.icon`).
- **component** → rendered directly via `<component :is>` (any icon source).

```ts
icon: "circle-check"                   // string → LUCIDE_ICON_CLASS lookup
import AlarmClock from "~icons/lucide/alarm-clock"
icon: AlarmClock                       // component → <component :is>
```

Both optional, so a custom type with neither still falls back to the per-type
default gracefully.

> Note: the string path resolves through the `LUCIDE_ICON_CLASS` literal map
> (Tailwind's JIT only emits a `lucide-<name>` mask class when that literal
> string appears in scanned source). A name not in the map won't render via the
> string path — pass a component, or use the `#icon-{type}` slot (e.g. a
> `FeatherIcon`), as the playground's `sla_breach` does.

---

## Other tweak channels (no markup)

- **`class` passthrough** — items use `inheritAttrs:false` + `:class="$attrs.class"`
  (frappe-ui idiom; no `twMerge`/`cn()` in this codebase, so it's array-append —
  override with non-conflicting / specific utilities).

---

## Try it — the playground

The living reference is **`/helpdesk/new`** (`apps/helpdesk/desk/src/pages/New.vue`,
"Activity Timeline — customization playground"): a doctype+document picker, a
scenario toggle, and a "View Consumer API" dialog showing each scenario's
snippet. Harness components live under
`apps/helpdesk/desk/src/pages/activity-playground/`.

| Scenario | Demonstrates |
| --- | --- |
| **basic** | built-in rendering, no customization |
| **slot** | override `#item-comment` with `PlaygroundComment` |
| **iconslot** | override content (`#item-comment`) **and** gutter (`#icon-comment`, FeatherIcon) |
| **region** | `#item-comment-header` + `#item-comment-footer`, body keeps its default |
| **custom** | merge a consumer-defined `sla_breach` row into a computed, re-sort, render via `#item-sla_breach` + `#icon-sla_breach` (FeatherIcon alert-triangle) |

The **custom** scenario is the proof that custom types need no composable/core
support: `PlaygroundTimeline.vue` builds a `displayActivities` computed that
merges the `sla_breach` row (only for that scenario), re-sorts, and applies
order — then renders it through the `#item-{type}` slot.

---

## Required exports (`index.ts`)

```ts
export { default as ActivityTimeline } from "./ActivityTimeline.vue";
export { default as EmailItem }   from "./EmailItem.vue";
export { default as CommentItem } from "./CommentItem.vue";
export { default as AuditItem }   from "./AuditItem.vue";
export { default as VersionItem } from "./VersionItem.vue";
export { useActivityTimeline } from "./useActivityTimeline";
export type {
  Activity, ActivityTimelineProps, AttachmentLogActivity, AuditActivity,
  BaseActivity, CommentActivity, CustomActivity, EmailActivity, EmailAttachment,
  UserInfo, VersionActivity,
} from "./types";
```

---

## Decisions — what shipped

- **Content dispatch:** `#item-{type}` slot (scoped `{ activity }`) > **default
  slot** (scoped `{ item }`) > built-in. No `#item` named generic slot; no
  `items` component-map prop.
- **Region sub-slots:** header/body/footer on **Comment + Email only**, surfaced
  at the timeline as `#item-{type}-{region}` and forwarded only when provided.
  Audit/attachment_log/version are Tier-1 only.
- **Gutter:** `#icon-{type}` slot (template) > envelope `icon?: string | Component`
  (string = `LUCIDE_ICON_CLASS` name, component = `<component :is>`) > per-type
  default. Symmetric with the content ladder.
- **Custom types:** `BaseActivity` / `CustomActivity` export + widened prop;
  consumer **merges its own rows client-side** and renders via `#item-{type}`.
  No composable injection.
- **Envelope:** `key` required; `timestamp?`, `author?`, `icon?` optional. **No
  `pin`/pinning.**
- **Audit subtypes:** `like` · `assigned` · `assignment_completed` · `workflow` ·
  `info` · `view`.

### Considered but not shipped

- `items` component-map prop and a generic `#item` named slot — replaced by the
  default slot exposing `{ item }`.
- `customActivities` injection into the composable (and `CustomActivitiesInput` /
  `UseActivityTimelineOptions`) — replaced by consumer-side merge.
- `pin: "start" | "end"` row pinning.
- `RenderableContent` (`string | { is, props }`) for the content region.
- Granular email sub-slots (`#actions`/`#recipients`/`#content`/`#attachments`) —
  replaced by header/body/footer regions.
- `order` as an options object — it's a positional param now.
