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
3. **Shared state, no event plumbing.** Controls that must agree bind the *same*
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

| | |
|---|---|
| **Props** | `doctype: string`, `hideLabel?: boolean` |
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

| | |
|---|---|
| **Props** | `doctype: string` |
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
  @save="persistView"
/>
```

| | |
|---|---|
| **Props** | `doctype: string` |
| **v-model:filters** | `FilterCondition[]` — **the same array Filter binds** |
| **v-model:fields** | `FilterField[]` — the surfaced fields (defaults to the doctype's `in_standard_filter` fields) |
| **v-model:customizing** | `boolean` — whether the strip is in customize/edit mode |
| **Emits** | `save: [FilterField[]]` — fired on an intentional save boundary; a good place to persist the view |

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

| | |
|---|---|
| **Props** | `doctype: string`, `hideLabel?: boolean`, `canReset?: boolean` |
| **v-model** | `Column[]` — `{ fieldname, label, width? }[]` (order = display order; no `width` = auto/flex) |
| **Emits** | `reset: []` — the inline-confirm "reset to defaults" gesture |

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
const view = useListView(doctype)

view.filters      // UseFilters    — { conditions: Ref<FilterCondition[]>, wire }
view.sort         // UseSort       — { by: Ref<Sort[]>, orderBy }
view.quickFilter  // UseQuickFilter— { fields, customizing, canCustomize }
view.columns      // UseColumns    — { shown, isCustomized, reset, wire, setWidth, resetWidth }

view.serialize()  // → ListViewSnapshot  (save the whole view as one JSON object)
view.restore(snapshot) // seed from a (possibly partial) snapshot
```

The `.wire` / `.orderBy` members are the **fetch projections** — the Frappe filter
list and `order_by` string you query with. The controls bind the *state* members
(`conditions`, `by`, `shown`, `fields`); you fetch with the *wire* members.

### Layout persistence (`serialize` / `restore`)

`serialize()` snapshots the whole view's customizable state — filters, sort, columns
(+ widths), quick-filter fields — as one plain-JSON object (`ListViewSnapshot`).
`restore(partial)` seeds the controls from it, applying only the members present. No
Meta is needed for a round-trip; conditions and quick-filter fields carry their own
field Meta. Save it wherever you like — a per-user preference, a named saved view:

```ts
function persistView() {
  localStorage.setItem(key, JSON.stringify(view.serialize()))
}
onMounted(() => {
  const saved = localStorage.getItem(key)
  if (saved) view.restore(JSON.parse(saved))
})
```

## `useListData(doctype, view)` — optional fetching

The half ADR-0001 leaves to the host. Opt in for doctype-agnostic data out of the
box, or skip it and keep your own data layer (the controls stay fetch-free either
way). It binds `frappe.client.get_list` (rows) + `get_count` (total) and refetches
from page 1 whenever a wire projection or the page length changes.

```ts
const data = useListData(doctype, view)

data.rows        // ComputedRef<Record<string, unknown>[]>  — the table's rows
data.loading     // first-page fetch in flight
data.rowCount    // rows currently loaded
data.totalCount  // total matching the filters
data.pageLength  // Ref<number> — ListFooter v-models this; a change refetches
data.loadMore()  // append the next page
data.reload()    // refetch page 1
```

---

## Putting it together

A complete toolbar: Filter + QuickFilter sharing one filter list, ColumnSettings
synced with the table's drag-resize, live rows via `useListData`, and layout
persistence on QuickFilter's `@save`. (This mirrors the `ListViewToolbar` story.)

```vue
<template>
  <ListViewShell :doctype="doctype">
    <template #toolbar>
      <QuickFilter
        v-model:filters="view.filters.conditions.value"
        v-model:fields="view.quickFilter.fields.value"
        v-model:customizing="view.quickFilter.customizing.value"
        :doctype="doctype"
        @save="persistView"
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
        <ListHeader @columnWidthUpdated="(e) => view.columns.setWidth(e.key, e.width)" />
        <ListRows />
      </ListView>
    </template>

    <template #footer>
      <ListFooter
        v-model="data.pageLength.value"
        :options="{ rowCount: data.rowCount.value, totalCount: data.totalCount.value }"
        @loadMore="data.loadMore()"
      />
    </template>
  </ListViewShell>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { ListView, ListHeader, ListRows, ListFooter, toast } from "frappe-ui";
import { ListViewShell, useListView, useListData } from "@framework/ui/ListView";
import { Filter } from "@framework/ui/Filter";
import { SortBy } from "@framework/ui/SortBy";
import { QuickFilter } from "@framework/ui/QuickFilter";
import { ColumnSettings } from "@framework/ui/ColumnSettings";

const props = defineProps<{ doctype: string }>();
const view = useListView(props.doctype);
const data = useListData(props.doctype, view);

const key = `listview:${props.doctype}`;
onMounted(() => {
  const saved = localStorage.getItem(key);
  if (saved) view.restore(JSON.parse(saved));
});
function persistView() {
  localStorage.setItem(key, JSON.stringify(view.serialize()));
  toast.success("View layout saved");
}
</script>
```

Mount it under `:key="doctype"` so switching doctypes reconstructs `useListView`.

### Bring your own data layer

Skip `useListData` and fetch with the wire projections yourself — the controls don't
care who fetches:

```ts
const view = useListView(doctype)
// view.filters.wire.value → Frappe filter list
// view.sort.orderBy.value → "modified desc"
// view.columns.wire.value → frappe-ui render columns
```
