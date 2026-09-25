# Persistence is deferred to the host; the library tops out at a View Snapshot

`useListView` exposes exactly two persistence affordances and **owns no saving
itself**: a reactive **`snapshot`** computed (a `ListViewSnapshot` — the whole
view's customizable state, the _save_ half) and a partial-aware **`restore`**
(the _load_ half). There is **no `ViewStorage` contract, no `usePersistedView`
glue, no storage adapters, and no `dirty` tracking** in the library. The save API
a host writes is simply `watch(view.snapshot, save)` — the host owns _when_ (per
change vs. explicit) and _where_ (which backend). This continues
[ADR-0001](0001-listview-controls-are-controlled-meta-driven.md)'s
controlled-component rule (controls touch no persistence) one level up to the
composite, and continues its "let the abstraction emerge when a second consumer
forces it" reasoning: with only two consumers today (CRM's backend and the Shell
story's `localStorage`), a persistence stack would be premature.

The library knows only the **current view _state_** (a **View Snapshot**), never
a saved **View** as a named/standard/public/owned entity — that whole concept
(CRM's `CRM View Settings`) stays in the consuming app, matching the glossary's
existing fence around CRM's "Views".

`restore` stays **rich-only** (it speaks `Partial<ListViewSnapshot>`, the fat,
Meta-carrying condition shape), and `snapshot` ↔ wire translation is done by the
**already-exported pure helpers** (`serializeFilters`/`parseFilters`,
`serializeColumns`/`parseColumns`, `serializeOrderBy`/`parseOrderBy`). The
generic skinny↔fat work therefore already lives _in_ the library; what stays in
a host is only its **own storage dialect** — e.g. CRM persists filters as a
legacy fieldname-keyed **dict** (`{"status": "Open"}`), not the library's
standard list-of-triples wire shape, so CRM writes a thin dict↔wire adapter a
greenfield app would never need.

## Considered Options

- **Ship the full stack now** (`ViewStorage` contract + `usePersistedView`
  autosave/explicit policy + `localStorageView`/`crmStandardView` adapters).
  Rejected: speculative abstraction against a single real backend — exactly what
  ADR-0001 rejected one level down. The shared shape can't be known until a
  second persistence backend (the foreseen generic `frappeDoctypeView`
  composable) makes it concrete; extract it then.
- **`useListView` owns autosave / a `storage` option.** Rejected: bakes a
  _policy_ (when and where to save) into headless state. The host must decide
  autosave vs. explicit per its own UX (CRM autosaves the standard view but saves
  named views only on an explicit button); the library hands over `snapshot` and
  stays out of it.
- **`dirty` / `markClean` in core.** Rejected: "changed since last save" is a
  persistence concept, and persistence is host-owned; dirty rides along in the
  host's watch (or the future `usePersistedView`).
- **A wire-accepting `restore` (`restoreWire`).** Rejected: duplicates the
  existing pure `parse*` helpers into the composable and re-couples it to wire
  shapes ADR-0003 kept outside the controls. The host calls one `parse*` helper
  before `restore` — the same "host owns persistence" responsibility.
- **`useListView` understands a first-class `View` entity** (id, isStandard,
  isPublic…). Rejected: drags CRM's Views concept into the shared library, the
  exact coupling the glossary and ADR-0001 fence off. The library tops out at an
  identity-less **View Snapshot**.
