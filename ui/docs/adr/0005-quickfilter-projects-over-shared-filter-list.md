# Quick Filter projects over a shared Filter list via canonical-operator ownership

The **Quick Filter** control is built in `@framework/ui` as a second **controlled
component** whose `v-model` is the _same_ `Filter[]` list the **Filter** control
binds (the condition model of [ADR-0003](0003-filter-control-ports-crm-onto-shared-fields.md)).
A new **`useListView(doctype)`** composable — the composite module's state owner
foreshadowed in [ADR-0002](0002-listview-module-layout.md) — owns that array (plus
`sorts` and the surfaced quick-filter fields) and hands the one ref to both
controls. Filter ↔ Quick Filter **sync is therefore automatic**: both mutate one
array, so there is no event plumbing between the two controls. This is the shared
composable [ADR-0001](0001-listview-controls-are-controlled-meta-driven.md)
deliberately deferred "until two controls actually need it" — Quick Filter is that
moment.

The real work is the **projection**: in our list model a field can carry several
conditions (`amount > 100 AND amount < 500`), so a quick filter cannot simply own
`filters[fieldname]` the way CRM's fieldname-keyed dict does. A quick filter owns
**only conditions on its field whose operator is in the quick filter's canonical
operator _set_ for that fieldtype** — `equals` for Check/Select/Date/Datetime,
`like` for the free-text types (Data/Text/Number/Duration), and for **Link** the
two-element set `[like, equals]` with `like` the default. Link gets both because
you rarely recall a record's exact name: a Link quick filter substring-searches by
default but can be flipped to an exact `equals` pick through a per-input operator
toggle (the `≈`/`=` button), which also swaps the value control — a text box for
`like`, a Link picker for `equals`. This is a dedicated
`quickFilterOperators(fieldtype)` table, a faithful port of CRM's
`applyQuickFilter`/`quickFilterList` mapping (extended only by the Link toggle) —
**not** a reuse of the popover's `getDefaultOperator` (which starts Date on
`between`, breaking the one-tap UX). Reads find the first owned condition for the
field and surface its value (and active operator); writes upsert that condition
under the active operator; an empty value removes it. A condition built in the
Filter popover with an operator _outside_ the set (e.g. `Status in [Open, Won]`)
is left untouched — the quick input shows empty for it, and setting the quick
filter **appends** a coexisting `Status equals …` condition rather than
overwriting the precise one. The helpers `quickValue(filters, field)`,
`quickOperator(filters, field)`, and `applyQuick(filters, field, value, operator?)`
are pure and frappe-ui-free, so the sync contract is unit-tested without a mounted
component.

A quick filter carries a **second, independent state slice** beyond its value: the
set of **surfaced fields** (which fields appear as inline inputs). It is an
optional `v-model:fields`, defaulting to a pure `getQuickFilterFields(fields)`
derivation from Meta — the fields flagged `in_standard_filter`, the Quick Filter
analog of `getFilterableFields` (no `get_quick_filters` endpoint, no CRM-Lead-
specific `converted` stripping, and — matching the server default — no `name`
field; `name` is reachable only through the customize/add picker, which draws from
`getFilterableFields`). The customize/add flow mutates that
model in session; a host _may_ bind it to persist the user's chosen quick filters
(CRM's `CRM Global Settings`), matching the controlled-component rule that the host
wires persistence. Surfaced-fields and values are independent: removing a field
from the customize list only hides its input — any existing `Filter[]` condition
survives and still shows in the Filter popover.

Two consequences fall out cleanly. Because our `like` condition stores the **bare**
value (`serializeFilters` wraps the `%`), read-back needs no `%`-stripping — unlike
CRM, which stores `['LIKE', '%v%']` and strips on read. And a **Check** quick
filter is a checkbox mapping checked → `equals "Yes"`, unchecked → condition
removed; it never emits `equals "No"`, matching CRM's `value ? set : delete`. The
value inputs are the shared `Fields` components ([ADR-0004](0004-fields-relocated-to-shared-module.md)),
not CRM's `FormControl`.

## Considered Options

- **Pass `useListView` into the controls (prop or provide/inject).** Rejected:
  couples both controls to the composable's API and breaks the controlled-component
  purity of ADR-0001. Binding the same `Filter[]` ref gives identical sync with
  zero coupling — neither control knows the composable exists.
- **QuickFilter owns its own `v-model`; the host reconciles into `Filter[]`.**
  Rejected: pushes the projection logic into every host instead of a shared,
  tested helper, and re-creates the cross-control event plumbing the shared ref
  removes.
- **Quick filter owns the first condition on its field, any operator.** Rejected:
  setting a quick filter would rewrite a precise popover-built condition (turn
  `Status in [Open, Won]` into `equals Closed`), destroying user intent — the very
  expressiveness the list model was chosen for in ADR-0003.
- **Replace (not append) when only a non-canonical condition exists.** Rejected for
  the same reason: a quick filter must never clobber a precise condition it doesn't
  own. Appending a coexisting `equals` is strictly more expressive than CRM's dict
  (which cannot hold both) and keeps `applyQuick` a pure, predictable upsert.
- **Tag quick-filter conditions with a `source: 'quick'` flag.** Rejected: leaks a
  UI provenance concern into the wire-facing `Filter` type that `serializeFilters`/
  `parseFilters` would have to strip — the operator already identifies ownership.
- **Reuse `getDefaultOperator` as the canonical operator.** Rejected: the popover's
  add-default and the quick filter's one-tap meaning are different concerns; reusing
  it would make a Date quick filter a `between` range, breaking the one-tap UX. The
  dedicated table also lets Link diverge deliberately (below) rather than inherit
  the popover's default.
- **A single fixed operator per fieldtype, with Link on `equals` (strict CRM
  parity).** Rejected: CRM treats Link quick filters as exact `equals` (and sneaks
  `name` in as a `Data`/`like` field to dodge this), but for a real Link you seldom
  recall the exact value. Giving Link a `[like, equals]` set with a per-input toggle
  — defaulting to `like` substring — is a deliberate one-feature divergence from CRM
  that keeps the projection a clean operator-set membership test rather than a
  special-cased `name`.
- **A free operator dropdown on every quick input (the full `getOperators` list).**
  Rejected: that re-creates the Filter popover inline and defeats the one-tap point.
  The toggle is scoped to the two operators a Link quick filter can mean (`like` vs
  `equals`); every other fieldtype keeps its single canonical operator and shows no
  toggle.
- **`useListView` takes a reactive doctype ref and clears state on an internal
  watch.** Rejected: the Shell already remounts controls via `:key="doctype"`, and
  `useDoctypeMeta` is cached per doctype string — reconstructing `useListView` per
  doctype is cheap and avoids a bespoke reset path.
