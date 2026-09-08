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
who owns it, belongs entirely to the consuming app. The library tops out here and
never owns a saved **View** entity; the host wires _when_ and _where_ to save it
([ADR-0007](docs/adr/0007-persistence-deferred-to-host-library-tops-out-at-view-snapshot.md)).
_Avoid_: view, saved view, view settings (all carry CRM's Views concept).

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
