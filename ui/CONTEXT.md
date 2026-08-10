# List View (shared @framework/ui)

The domain of the reusable doctype list-view experience being extracted from CRM
into `@framework/ui`: the toolbar controls a user manipulates to shape a list
(sort, filter, columns, quick filters) and the composite that assembles them.

## Language

**List View Controls**:
The four toolbar pieces a user manipulates to shape a doctype list — **SortBy**,
**Filter**, **Column Settings**, and **Quick Filter**. Each is an independent,
controlled component that owns one slice of view state.
_Avoid_: "view controls" (CRM's name; it carries the CRM-specific Views concept).

**Sort**:
A single ordering rule: a `fieldname` plus a `direction` (`asc`/`desc`). A list's
ordering is an ordered list of Sorts.
_Avoid_: order, ordering rule.

**order_by**:
The Frappe wire form of an ordering — a comma-joined string like
`"modified desc, name asc"`. The serialized form of a list of **Sort**s.
_Avoid_: sort string.

**Filter**:
A precise, fieldtype-aware condition on a doctype field, set through the Filter
control's popover. The full/advanced way to narrow a list.

**Quick Filter**:
A pre-chosen field surfaced inline in the toolbar for one-tap narrowing. A
convenience projection over **Filter**s — a Quick Filter and its matching
**Filter** describe the same underlying condition and stay in sync.
_Avoid_: inline filter.

**Column**:
One shown column in the list: a `fieldname`, a (user-overridable) `label`, and an
optional CSS `width` (`"11rem"`, `"120px"`). The Column Settings control's state is
an ordered list of Columns — presence means shown, array order is display order, and
`width` is the slice a column resize co-writes. A column's `align`/`type`/`options`
are not stored here; they are derived from **Meta** at render/serialize time.
_Avoid_: field, column setting (the control, not the datum), key (CRM's `key` ≙ `fieldname`).

**Field Options**:
The list of a doctype's fields a control offers (e.g. SortBy's sortable fields).
Derived client-side from doctype **Meta**, not from a CRM endpoint.
_Avoid_: sort_options, filterable fields (CRM endpoint names).

**Meta**:
A doctype's field definitions, fetched via the shared `useDoctypeMeta`
composable. The single source from which Field Options are derived.

**Controlled component**:
A control that owns only its own state slice via `v-model` plus a `doctype`,
emits changes, and never touches a data-fetching resource or persistence. The
host wires fetching, persistence, and cross-control sync.
_Avoid_: connected component, smart component.

**View Snapshot**:
The serialized, persist-able capture of a List View's state — its **Filter**s,
**Sort**s, **Column**s, and surfaced **Quick Filter** fields. The unit a host's
persistence layer is handed. It carries **no identity, ownership, or named-View
concept** — whether this is a "standard", public, pinned, or named **View**, and
who owns it, belongs entirely to the **Saved View** that points at it. `useListView`
tops out here and owns no saving; a host or the opt-in `useSavedViews` decides
_when_ and _where_
([ADR-0007](docs/adr/0007-persistence-deferred-to-host-library-tops-out-at-view-snapshot.md),
[ADR-0008](docs/adr/0008-saved-view-is-a-framework-entity-so-the-library-may-own-its-persistence.md)).
_Avoid_: view, view settings (CRM's `CRM View Settings` is a different, app-owned thing).

**Saved View**:
The framework DocType (`frappe/desk/doctype/saved_view`) that gives a **View
Snapshot** an identity: a `label`, an `icon`, the `reference_doctype` it belongs to,
a `type` (`list` / `group_by` / `kanban`), and an owning `user` — empty meaning
shared with everyone. Its `filters` / `order_by` / `columns` are stored in the
library's own wire shapes, so the existing `parse*` helpers are the whole
translation layer. Owned by the opt-in **`SavedViews`** module (`useSavedViews`),
never by `useListView`. That module owns what a view _is_ — its label, its snapshot,
its lifecycle. Where it sits is **Placement** and **Arrangement**, which belong to
the sibling `Navigation/` module; the two are composed by a host that needs both.
_Avoid_: view settings, CRM view (the legacy `CRM View Settings` record).

**Navigation Section**:
A labelled, ordered section of the **Navigation Sidebar** (e.g. "Views", "Pipeline") — a
`Navigation Section` holding a child table of **Navigation Item**s whose `idx` is
the canonical order. Its identity is `(app, reference_doctype, user)` — its
**Navigation Scope** plus its owner. A section with no `user` is shared; one with
a `user` is either that user's own section or, when `overrides` is set, their
personal reordering and hiding of a shared section. A **Saved View** in no section
is _unplaced_: it exists, but the sidebar doesn't show it — the _pool_ the
sidebar's + menu offers to add back. Removing a view from the sidebar unplaces it;
it is not a deletion.
_Avoid_: group, folder (`Saved View Group` was this record's earlier name).

**Navigation Item**:
One row of a **Navigation Section**, and one row of the sidebar. Its `type` says what
it points at: a `view` opens a **Saved View**, a `link` opens a URL. `view` is
therefore optional, and a **Count** is taken for views alone — every other type has
none, and the row shows no badge. An item carries its own `label` and `icon`; for a
`view` those are an optional *override* that falls back to the view's, which lets a
user shorten a shared view's name on their own sidebar without renaming it for
everybody, while a type with no record behind it has nowhere else to get them and so
must be given a label. The row's `name` is its identity — what an **Overlay** points
at and what **Arrangement** reorders by — because a link has no view to be found by
and two rows may hold the same one. Client-side it arrives as a `NavigationItem`
with `label` and `icon` already resolved and `view` set to `null` for every non-view
type, so a renderer never asks what type it is looking at just to draw it.
_Avoid_: entry, link (a link is one type of item, not the concept).

**extras section**:
A **Navigation Section** holding no `view` items — the block of links and shortcuts
the **Navigation Sidebar** sinks below the views, draws with no heading, and rules
off. **Derived, never flagged**: `isExtrasSection` reads what the section holds, so a
section that later gains a view simply stops being extras, with no field to fall out
of sync. Derived over what the section *holds*, not over what is left after a user's
hidden rows are dropped — otherwise hiding the last view in a mixed section would
silently restyle it for that one user. It is a rendering rule only: edit mode still
lists such a section under its label, in server order.
_Avoid_: footer, other, misc section.

**Navigation Scope**:
Where a **Navigation Section** lives: the pair `(app, reference_doctype)`, modelled
as a frozen `Scope` in `navigation_section/scope.py` and threaded through every read
— the sidebar, the overlays, the personal sections, the counts cache key, the pool,
and the section a newly placed view lands in. `app` is what keeps two apps on one
site from colliding: each app names its own (`crm`; a caller that names none falls
back to `frappe`), and neither ever sees the other's sections. A blank `app` is _not_
the framework's — it is its own value, so a row that should not exist fails a scope
comparison loudly instead of being misfiled into `frappe`. Client-side the same pair
is a `NavigationScope`, and every call not addressed to an existing record carries
it: a scope-wide read filters by it, a find-or-create needs it to know what to make.
A call naming a section passes the name alone — that record already knows its scope.
_Avoid_: namespace, tenant (neither of those is about one app's navigation).

**app-level section**:
A **Navigation Section** with an empty `reference_doctype` — navigation belonging to
the app itself rather than to any one doctype's sidebar, which is where a rail
belongs. `Scope.is_app_level` is the test, and since an unset Link reads back as `""`
over one path and `None` over another, the filter that finds one is the shared
`UNSET`. Nothing in the framework renders these yet; the scope exists so a
whole-app nav surface has a valid home rather than borrowing some doctype's. Their
views may each name a different doctype, so a count is taken against the view's own
`reference_doctype`, never the sidebar's.
_Avoid_: global section, rail section (the rail is one renderer of these, not the
only possible one).

**Overlay**:
A user's private deltas over a shared **Navigation Section** — their rows' order and
hidden flags, plus, on the record itself, where they moved the section (`sequence`)
and whether they hid it (`hidden`), and nothing else. A shared section's own `hidden`
is never written or read: hiding is a statement about one's own sidebar, so it lives
here for everybody, and a manager who wants a section gone for the site deletes it.
Stored as a `Navigation Section` with `overrides`
pointing at the shared one, in that section's own **Navigation Scope**; an overlay
may not reach across scopes. Its rows name the shared rows they delta by *row name*,
in `overrides` — row identity rather than view identity, because a `link` has no view
to be matched on. Because it holds deltas rather than a copy, a manager's later edits
still reach it: a row it never mentions was added (and lands at the end of the
section), a row only it mentions was removed (and vanishes).
`get_sidebar` resolves it server-side, so a client is handed the final arrangement.
_Avoid_: fork, private copy (both suggest a snapshot, which is what this is not).

**Placement**:
Which **Navigation Section**, if any, holds a view — what `saved_view/api.py` mutates
server-side and `useNavigation` drives from the client.
Placement is what sets visibility, a shared section being public and a personal one
not, which is why moving a view across that line is confirmed.

**Arrangement**:
Where an item sits once it _is_ placed: its order within a section, and whether the
user has hidden it — and the same two for the sections themselves. Deliberately distinct from **Placement**, because the two have
different permission shapes — anyone may arrange the shared area (into their own
**Overlay**), but only a manager places anything in it. Hence `arrange_items`
rejects a row list that gained or lost a row. It takes `[{name, hidden}]` and
*repositions* the shared section's existing rows rather than rewriting them, since a
row's name is what every **Overlay** points at.
_Avoid_: layout, sort order.

**Navigation Sidebar**:
The doctype-scoped panel that lists a user's **Navigation Section**s and their
**Saved View**s and switches between them. One batteries-included presentation of
`useNavigation`, the way the **Shell** is one presentation of `useListView` — the
composable is the contract, and a host is free to render the same sections as a
dropdown or a palette instead. Hence the module is `Navigation/`, not
`NavigationSidebar/`.
_Avoid_: view sidebar (`ViewSidebar` was this component's earlier name — the panel
holds more than views).

**Composite List View**:
The shared module that assembles the controls (and, later, the table, footer,
selection banner, and a `useListView` state composable) into a full list view.
The home of the integration "shell" story used to chase pixel parity with CRM.

**Shell story**:
The combined story in the Composite List View module that mounts the controls
together against a real doctype to verify pixel parity with CRM's list view.
Distinct from each control's own isolated story.

## Example dialogue

— "When I change the SortBy chip, does it write `order_by` back to the resource?"
— "No. SortBy is a **controlled component** — its `v-model` is a list of
**Sort**s. It just emits the new array; the host serializes it to **order_by**
and refetches."
— "And where do the sortable fields come from — the `sort_options` endpoint?"
— "No CRM endpoint. **Field Options** are derived from the doctype's **Meta**."
— "If I set a **Quick Filter** for Status, does the Status **Filter** update too?"
— "Yes — a Quick Filter is a projection over Filters; they describe the same
condition and stay in sync once the shared composable lands."
