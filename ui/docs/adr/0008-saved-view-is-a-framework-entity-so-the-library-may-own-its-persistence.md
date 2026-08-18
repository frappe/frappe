# Saved View is a framework entity, so the library may own its persistence

**Supersedes [ADR-0007](0007-persistence-deferred-to-host-library-tops-out-at-view-snapshot.md)**
(in part). `useListView` is unchanged — it stays snapshot-only and owns no saving.
What changes is the _fence_: an **opt-in `useSavedViews` module may own the
persistence of a `Saved View`**, because `Saved View` is now a Frappe Framework
DocType (`frappe/desk/doctype/saved_view`), not a CRM one.

ADR-0007 drew its line around a **consumer**: "CRM's `CRM View Settings` stays in
the consuming app." That was right — a shared library must not learn one app's
schema. But it stated the rule as though _any_ named-View entity were app
territory, and that over-reached. The thing being fenced out was CRM-specific
endpoints and CRM's fieldname-keyed filter dict, not the _concept_ of a stored
view. With `Saved View` / `Saved View Group` shipping in the framework, every
Frappe app has them for free, exactly as every app has **Meta** — and FP3 already
says deriving from what every app already has is the app-agnostic move. Persisting
to a framework DocType through stock whitelisted methods couples the library to
Frappe, which it is already and by design; it couples it to no app.

ADR-0007 also named its own exit condition: a persistence abstraction should wait
until "a second persistence backend (the foreseen generic `frappeDoctypeView`
composable) makes it concrete; extract it then." That second backend has arrived
and is the one being built here. This ADR is that extraction, not a reversal.

## What holds, and what moves

**`useListView` does not change.** It exposes `snapshot` + `restore` and nothing
else; there is still no `dirty` tracking, no `storage` option, no autosave policy
inside it. Every rejection in ADR-0007's options list that targeted _`useListView`
itself_ still stands, for the reasons given there: a composite that bakes in when
and where to save is not reusable.

**Persistence moves into a sibling module, not into the core.** `useSavedViews` is
a separate, opt-in composable in its own module (ADR-0002's one-module-per-concern
layout) — the same relationship `useListData` already has to `useListView`. A host
that wants nothing to do with `Saved View` imports `useListView` alone and is
unaffected; the two compose through the public `snapshot` / `restore` seam rather
than through internals.

**The bridge stays the snapshot.** `useSavedViews` reads a `Saved View` and hands
`useListView.restore` a `Partial<ListViewSnapshot>`; it never reaches into
`filters.conditions` or `columns.shown`. So the identity-carrying entity (id,
label, owner, group placement) lives entirely in `useSavedViews`, and
`ListViewSnapshot` stays identity-less exactly as ADR-0007 required. The fence
ADR-0007 built is still there — it just now sits between `useSavedViews` and
`useListView` rather than between the library and the host.

**A `Saved View` stores the library's wire shapes.** `filters` is the
list-of-triples `WireFilters` from ADR-0003, `order_by` the `order_by` string,
`columns` the `WireColumn[]` render shape — so the existing pure helpers
(`parseFilters` / `parseColumns` / `parseOrderBy`) are the whole translation layer
and no new dialect is invented. CRM's legacy fieldname-keyed dict is not adopted;
apps migrating off `CRM View Settings` convert on the way in (a data migration),
not on every read.

**The write half is placement-shaped, and permission lives on the server.** What
`useSavedViews` mutates is mostly _where_ a view sits, not what it contains: a
view's section is a child row in a `Saved View Group`, and having no section at
all is a real state (the pool) distinct from being deleted. That is why the write
surface is a handful of placement endpoints rather than one `save(view)` —
membership is not a field write. Label and icon, which _are_ field writes, go
through stock `frappe.client.set_value`.

Visibility follows from placement: a view with no `user` is shared, and only a
manager may change the shared area. The controllers enforce that; `get_sidebar`
returns a `can_manage_shared` flag purely so the client can hide affordances the
server would reject anyway. The flag is a courtesy, never the gate — which is why
`getViewActions` is a pure function tested against the same rule the server
applies, rather than the place the rule is decided.

**Arrangement is a separate surface from placement, and the server resolves it.**
_Placement_ decides whether a view is on the sidebar at all; _arrangement_ decides
where it sits once it is. They are different endpoints because they have different
permission shapes: placing a view in the shared area is a manager's call, but
anyone may reorder or hide what they see there — that writes a per-user **overlay**
(`Saved View Group` with `overrides` set) holding only deltas, never a fork of the
shared group. `arrange_views` therefore rejects a row list that gained or lost a
view: a client that tried to place something by arranging it is out of date.

Reconciliation follows from storing only deltas rather than a copy: a view the
overlay never mentions is one the manager added (so it appears at the end), and a
view only the overlay mentions is one the manager removed (so it vanishes). No
migration of anyone's overlay is needed when the shared group changes.

`get_sidebar` applies the caller's overlays before returning, so the client
receives the final arrangement and never merges anything. The corollary is that
hidden views must still come over — `visibleGroups` filters them for rendering
while `groups` keeps them, because edit mode has to show a hidden view to offer an
unhide, and a route naming one must still resolve.

**A manager rearranging a shared section is asked which they meant.** It is the one
operation with two legitimate destinations — publishing the order everyone starts
from, or tidying their own sidebar — and guessing either way is wrong often enough
to be worth the click. Everyone else has exactly one destination and is not asked.
Saving for everyone also drops the manager's own overlay, or they would be the one
user unable to see what they just published.

**Restoring is partial.** A `Saved View` carries no quick-filter field list, so
`useSavedViews` restores `filters` / `sort` / `columns` and leaves
`quickFilterFields` at its Meta default — which is precisely what ADR-0007's
partial-aware `restore` was built to allow.

## Considered Options

- **Keep ADR-0007 intact and put `useSavedViews` in each consuming app.**
  Rejected: it is the same composable in every app. The fence's purpose was to
  keep _one app's_ schema out of a shared library; a framework DocType is not one
  app's schema, and honoring the letter of ADR-0007 here would force every Frappe
  app to rewrite identical fetch/parse/restore glue. That is the duplication FP1
  and ADR-0002 exist to prevent.
- **Carve a quiet exception in ADR-0007's text.** Rejected on process grounds:
  PHILOSOPHY.md's own instruction is to propose an edit when a principle stops
  being generative, not to special-case it. Hence this ADR plus an amendment to
  FP2 rather than an edited ADR-0007.
- **Move persistence into `useListView` now that the entity is framework-owned.**
  Rejected for every reason ADR-0007 gave. Framework-ownership of the _entity_
  says nothing about whether a _composite_ should bake in save policy — a host
  still chooses autosave vs. explicit save, and the tracer's read-only path must
  not drag a writer into core.
- **Have `useSavedViews` write through `useListView`'s internals** (setting
  `filters.conditions` directly) to avoid a partial-restore edge. Rejected:
  re-couples the two modules to each other's private state and makes
  `ListViewSnapshot` no longer the single load contract.
- **Let a user's rearrange of a shared section fork it into a private copy.**
  Rejected: a copy is a snapshot, so every later change a manager makes — a new
  view, a deleted one, a rename — would stop reaching anyone who had ever dragged
  a row. The delta overlay keeps membership in one place and lets the manager's
  edits flow through it.
- **Resolve overlays on the client.** Rejected: it puts the reconciliation rules in
  every host that renders the sidebar, including hosts that render a palette rather
  than a panel, and makes them untestable without mounting a component. Resolving
  server-side keeps `apply_overlay` a pure function with unit tests and leaves the
  client with a list to render.
- **Store a `Saved View`'s filters in CRM's fieldname-keyed dict** so CRM needs no
  migration. Rejected: the dict cannot express one field filtered twice — the
  exact defect ADR-0003 rejected frappe-ui's `ListFilter` over. A new framework
  entity should not be born with a known-lossy encoding to spare one app a
  one-time patch.
