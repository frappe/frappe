# List View controls — usage guide

The reusable DocType list-view experience, extracted from CRM into `@framework/ui`.
It is a set of **controlled, meta-driven** controls — **SortBy**, **Filter**,
**QuickFilter**, **ColumnSettings** — plus two composables that join them
(`useListView`) and optionally fetch rows (`useListData`).

This guide covers what each piece exports, how the pieces fit together, and a full
copy-paste integration. For the vocabulary (Sort, Filter, Column, Field Options,
Meta…) see [`CONTEXT.md`](../../../CONTEXT.md); for the design rationale see the
ADRs under [`ui/docs/adr/`](../../../docs/adr/).

## The mental model

Three rules explain everything else:

1. **Controlled.** Every control owns only its own state slice via `v-model` and
   takes a `doctype`. It never fetches data and never persists anything. You give it
   state, it gives you back edited state.
2. **Meta-driven.** Each control derives its **Field Options** (which fields it
   offers) client-side from the doctype's Meta (via the shared `useDoctypeMeta`),
   not from a backend endpoint.
3. **Shared state, no event plumbing.** Controls that must agree bind the _same_
   ref. Filter and QuickFilter both `v-model` the same `FilterCondition[]`, so a
   quick input and its matching advanced condition stay in sync with zero wiring.
   ColumnSettings and the table's drag-resize both bind the same `Column[]`.

The host (your app) owns the three things the controls deliberately don't: fetching,
persistence, and cross-control wiring. `useListView` does the wiring for you;
`useListData` does the fetching for you if you want it.

## Quick start

The shortest path is the two composables — let them own state and fetching, and
bind the controls to them.

```vue
<script setup lang="ts">
import { useListView, useListData } from "@framework/ui/ListView";

const props = defineProps<{ doctype: string }>();
const view = useListView(props.doctype); // owns filter/sort/column/quick-filter state
const data = useListData(props.doctype, view); // turns wire projections into rows
</script>
```

`view` exposes one namespaced member per control; bind each control to its slice
(full example at the bottom). `data` gives you `rows`, `loading`, counts, and paging.

> `useListView` takes `doctype` **by value**, not a ref. To switch doctypes,
> remount with `:key="doctype"` — that reconstructs the state cheaply (Meta is
> cached per doctype) and resets the controls, with no internal reset watcher.

---

## SortBy

The sort control. Binds an ordered list of `Sort` rules.

```vue
<SortBy v-model="view.sort.by.value" :doctype="doctype" />
```

|             |                                                          |
| ----------- | -------------------------------------------------------- |
| **Props**   | `doctype: string`, `hideLabel?: boolean`                 |
| **v-model** | `Sort[]` — `{ fieldname, direction: "asc" \| "desc" }[]` |

**Helpers**

- `getSortOptions(fields)` → `SortOption[]` — sortable Field Options from Meta.
- `serializeOrderBy(sorts)` → `"modified desc, name asc"` — the Frappe `order_by` wire string.
- `parseOrderBy(orderBy)` → `Sort[]` — the inverse, for hosts that store an `order_by` string.

## Filter

The full/advanced filter control: a popover of fieldtype-aware conditions, multiple
conditions per field, `in`/`not in` via `MultiSelect` on option fields, and value
carry-over when you change a row's field.

```vue
<Filter v-model="view.filters.conditions.value" :doctype="doctype" />
```

|             |                                                                  |
| ----------- | ---------------------------------------------------------------- |
| **Props**   | `doctype: string`                                                |
| **v-model** | `FilterCondition[]` — `{ fieldname, operator, value, field? }[]` |

`FilterOperator` is CRM's UI vocabulary (`equals`, `like`, `in`, `between`,
`timespan`, …), mapped to the Frappe wire form by `serializeFilters`.

**Helpers**

- `getFilterableFields(fields, doctype)` → `FilterField[]` — filterable Field Options from Meta.
- `getOperators(fieldtype)` / `getDefaultOperator(fieldtype)` / `getDefaultValue(field)` — per-fieldtype operator sets and defaults.
- `serializeFilters(conditions)` → `WireFilters` — the Frappe filter list you fetch with.
- `parseFilters(...)` → `FilterCondition[]` — the inverse, for hosts that store a wire filter list.

## QuickFilter

Inline quick-filter inputs in the toolbar — a convenience **projection over the same
filter list** Filter edits. A quick input and its matching advanced condition
describe the same underlying condition. Overflow collapses behind a "more" toggle;
Link fields get a like/equals operator toggle; clearing a quick input removes every
condition it owns.

```vue
<QuickFilter
  v-model:filters="view.filters.conditions.value"
  v-model:fields="view.quickFilter.fields.value"
  v-model:customizing="view.quickFilter.customizing.value"
  :doctype="doctype"
/>
```

|                         |                                                                                                                                                                                                                                                                                                                                       |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Props**               | `doctype: string`                                                                                                                                                                                                                                                                                                                     |
| **v-model:filters**     | `FilterCondition[]` — **the same array Filter binds**                                                                                                                                                                                                                                                                                 |
| **v-model:fields**      | `FilterField[]` — the surfaced fields (defaults to the doctype's `in_standard_filter` fields)                                                                                                                                                                                                                                         |
| **v-model:customizing** | `boolean` — whether the strip is in customize/edit mode                                                                                                                                                                                                                                                                               |
| **Emits**               | `done: [FilterField[]]` — fired when the user clicks **Done** to leave the _customize-which-fields_ surface. Field edits are already live via `v-model:fields`, so this is **not** a save (the `view.snapshot` watcher persists them). You only need it if you opted out of binding `v-model:fields` and want the final surfaced set. |

`customizing` and `canCustomize` live on the shared composable, so a "Customize"
trigger can sit anywhere in your toolbar (not just beside QuickFilter) and still
drive the strip.

**Helpers** (pure projection by canonical operator): `getQuickFilterFields`,
`quickFilterOperator(s)`, `hasOperatorToggle`, `quickValue`, `quickOperator`,
`applyQuick`.

## ColumnSettings

Add / reorder / remove columns, rename them, and resize widths — kept in sync with
the frappe-ui `ListView`'s drag-resize.

```vue
<ColumnSettings
  v-model="view.columns.shown.value"
  :doctype="doctype"
  :can-reset="view.columns.isCustomized.value"
  @reset="view.columns.reset()"
/>
```

|             |                                                                                               |
| ----------- | --------------------------------------------------------------------------------------------- |
| **Props**   | `doctype: string`, `hideLabel?: boolean`, `canReset?: boolean`                                |
| **v-model** | `Column[]` — `{ fieldname, label, width? }[]` (order = display order; no `width` = auto/flex) |
| **Emits**   | `reset: []` — the inline-confirm "reset to defaults" gesture                                  |

A column with no `width` flexes to fill; only a resized column carries a fixed
`width`, and dropping it (double-click the resizer) returns it to auto. `align` /
`type` / `options` are derived from Meta at serialize time, not stored.

**Helpers**: `getDefaultColumns(fields, titleField)`, `serializeColumns` →
`WireColumn[]` (the frappe-ui render shape), `parseColumns`, `applyColumnWidth`,
`clearColumnWidth`.

---

## `useListView(doctype)` — the state owner

Composes the four per-control composables into one namespaced surface so you can see
at a glance which member drives which control. It owns no state itself; each slice
lives in its co-located composable and reads Meta itself (cached).

```ts
const view = useListView(doctype);

view.filters; // UseFilters    — { conditions: Ref<FilterCondition[]>, wire }
view.sort; // UseSort       — { by: Ref<Sort[]>, orderBy }
view.quickFilter; // UseQuickFilter— { fields, customizing, canCustomize }
view.columns; // UseColumns    — { shown, isCustomized, reset, wire, setWidth, resetWidth }

view.snapshot; // ComputedRef<ListViewSnapshot>  (the whole view as one JSON object)
view.restore(snapshot); // seed from a (possibly partial) snapshot
```

The `.wire` / `.orderBy` members are the **fetch projections** — the Frappe filter
list and `order_by` string you query with. The controls bind the _state_ members
(`conditions`, `by`, `shown`, `fields`); you fetch with the _wire_ members.

### Saving changes — read this first

**You do not save controls individually.** There is no "save the Filter", "save the
SortBy", or "save the Columns". All four controls write into one object,
`view.snapshot`, and **any** change replaces it with a new value. So you wire **one**
watcher and it persists everything:

```ts
watch(view.snapshot, (snap) => saveView(snap)); // saves ALL of the below
```

Every one of these triggers that single watcher — there is nothing else to wire:

| The user…                           | …mutates                           | …so `view.snapshot` changes and your watcher saves |
| ----------------------------------- | ---------------------------------- | -------------------------------------------------- |
| edits a **Filter**                  | `view.filters.conditions`          | ✅                                                 |
| reorders/changes **SortBy**         | `view.sort.by`                     | ✅                                                 |
| **adds / removes** a column         | `view.columns.shown`               | ✅                                                 |
| **resizes** a column (drag header)  | `view.columns.shown` (width)       | ✅                                                 |
| edits a **Quick Filter** value      | `view.filters.conditions` (shared) | ✅                                                 |
| customizes which quick filters show | `view.quickFilter.fields`          | ✅                                                 |

> `snapshot` is a fresh object **only when a control's state actually changes**, so
> the watcher fires once per real edit — no `deep: true`, no spurious saves. Resize
> and add/remove are not special cases: they both edit `view.columns.shown`, which is
> in the snapshot.

`QuickFilter`'s `@done` event is **not** how saving works — it is one _optional
extra_ explicit boundary (the "Done customizing" button). With the watcher above you
do not need it at all.

**The library owns no saving** ([ADR-0007](../../../docs/adr/0007-persistence-deferred-to-host-library-tops-out-at-view-snapshot.md));
the host decides _when_ and _where_. Two common shapes:

```ts
// (a) Autosave to a backend on every change (debounced so a drag-resize or fast
//     typing doesn't spam the server). `saveView` is YOUR function — see below.
watch(view.snapshot, useDebounceFn(saveView, 500));

// (b) Or save only on an explicit "Save" button:
function onSaveClick() {
  saveView(view.snapshot.value);
}
```

#### Saving to the database (the actual RPC)

`view.snapshot` is the _rich_ shape (conditions carry field Meta). Your DocType wants
the _compact wire_ shape — convert with the library's `serialize*` helpers, then call
your own whitelisted method:

```ts
import { call } from "frappe-ui";
import { serializeFilters } from "@framework/ui/Filter";
import { serializeOrderBy } from "@framework/ui/SortBy";
import { serializeColumns } from "@framework/ui/ColumnSettings";

async function saveView(snap: ListViewSnapshot) {
  await call("my_app.api.save_list_view", {
    doctype: props.doctype,
    filters: serializeFilters(snap.filters), // → [[fieldname, op, value], …]
    order_by: serializeOrderBy(snap.sort), // → "modified desc, name asc"
    columns: serializeColumns(snap.columns, fields), // → [{ key, label, width }, …]
  });
}
```

#### Loading it back (`restore`)

On mount, read your row, turn the wire shape back into the rich shape with the
matching `parse*` helpers, and hand it to `restore` (which applies only the parts you
pass):

```ts
onMounted(async () => {
  const saved = await call("my_app.api.get_list_view", {
    doctype: props.doctype,
  });
  if (!saved) return;
  view.restore({
    filters: parseFilters(fields, saved.filters),
    sort: parseOrderBy(saved.order_by),
    columns: parseColumns(saved.columns),
  });
});
```

`restore` is **partial** — it applies only the keys you pass and leaves the rest at
their defaults, so it doubles as a per-slice restore. Hand it just one member to
restore that one control (a "reset filters only", or loading slices saved
separately):

```ts
view.restore({ columns: parseColumns(saved.columns) }); // only columns; filters/sort untouched
view.restore({ filters: parseFilters(fields, saved.filters) }); // only filters
```

Because each control is controlled and v-models its own slice, you can equally assign
the ref directly — `view.columns.shown.value = parseColumns(saved.columns)` — without
going through `restore` at all. The slice (filters / sort / columns /
quickFilterFields) is the atom on both sides: `snapshot` saves them all, `restore`
loads any subset.

> Saving to `localStorage` instead? Skip the helpers entirely — the snapshot is
> plain JSON: `localStorage.setItem(key, JSON.stringify(view.snapshot.value))` /
> `view.restore(JSON.parse(localStorage.getItem(key)))`.

## `useListData(doctype, view)` — optional fetching

The half ADR-0001 leaves to the host. Opt in for doctype-agnostic data out of the
box, or skip it and keep your own data layer (the controls stay fetch-free either
way). It binds `frappe.client.get_list` (rows) + `get_count` (total) and refetches
from page 1 whenever a wire projection or the page length changes.

```ts
const data = useListData(doctype, view);

data.rows; // ComputedRef<Record<string, unknown>[]>  — the table's rows
data.loading; // first-page fetch in flight
data.rowCount; // rows currently loaded
data.totalCount; // total matching the filters
data.pageLength; // Ref<number> — ListFooter v-models this; a change refetches
data.loadMore(); // append the next page
data.reload(); // refetch page 1
```

---

## Putting it together

A complete toolbar: Filter + QuickFilter sharing one filter list, ColumnSettings
synced with the table's drag-resize, live rows via `useListData`, and **autosave via
a single `watch(view.snapshot, …)`** — which covers filter, sort, and every column
add/remove/resize, not just quick filters. (This mirrors the `ListViewToolbar` story.)

```vue
<template>
  <ListViewShell :doctype="doctype">
    <template #toolbar>
      <QuickFilter
        v-model:filters="view.filters.conditions.value"
        v-model:fields="view.quickFilter.fields.value"
        v-model:customizing="view.quickFilter.customizing.value"
        :doctype="doctype"
      />
      <template v-if="!view.quickFilter.customizing.value">
        <Filter v-model="view.filters.conditions.value" :doctype="doctype" />
        <SortBy v-model="view.sort.by.value" :doctype="doctype" />
        <ColumnSettings
          v-model="view.columns.shown.value"
          :doctype="doctype"
          :can-reset="view.columns.isCustomized.value"
          @reset="view.columns.reset()"
        />
      </template>
    </template>

    <template #table>
      <ListView
        :columns="view.columns.wire.value"
        :rows="data.rows.value"
        row-key="name"
        :options="{ selectable: true, resizeColumn: true }"
      >
        <ListHeader
          @columnWidthUpdated="(e) => view.columns.setWidth(e.key, e.width)"
        />
        <ListRows />
      </ListView>
    </template>

    <template #footer>
      <ListFooter
        v-model="data.pageLength.value"
        :options="{
          rowCount: data.rowCount.value,
          totalCount: data.totalCount.value,
        }"
        @loadMore="data.loadMore()"
      />
    </template>
  </ListViewShell>
</template>

<script setup lang="ts">
import { onMounted, watch } from "vue";
import { useDebounceFn } from "@vueuse/core";
import { ListView, ListHeader, ListRows, ListFooter } from "frappe-ui";
import {
  ListViewShell,
  useListView,
  useListData,
} from "@framework/ui/ListView";
import { Filter } from "@framework/ui/Filter";
import { SortBy } from "@framework/ui/SortBy";
import { QuickFilter } from "@framework/ui/QuickFilter";
import { ColumnSettings } from "@framework/ui/ColumnSettings";

const props = defineProps<{ doctype: string }>();
const view = useListView(props.doctype);
const data = useListData(props.doctype, view);

const key = `listview:${props.doctype}`;

// Load once on mount.
onMounted(() => {
  const saved = localStorage.getItem(key);
  if (saved) view.restore(JSON.parse(saved));
});

// Autosave on ANY change — filter, sort, column add/remove/resize, quick filter.
// One watcher; debounced so a drag-resize doesn't write on every pixel. Swap the
// body for your `call("my_app.api.save_list_view", …)` to persist to the database.
watch(
  view.snapshot,
  useDebounceFn((snap) => localStorage.setItem(key, JSON.stringify(snap)), 500)
);
</script>
```

Mount it under `:key="doctype"` so switching doctypes reconstructs `useListView`.

### Bring your own data layer

Skip `useListData` and fetch with the wire projections yourself — the controls don't
care who fetches:

```ts
const view = useListView(doctype);
// view.filters.wire.value → Frappe filter list
// view.sort.orderBy.value → "modified desc"
// view.columns.wire.value → frappe-ui render columns
```
