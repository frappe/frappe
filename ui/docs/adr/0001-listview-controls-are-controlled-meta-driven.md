# List View controls are controlled, meta-driven components

CRM's SortBy/Filter/ColumnSettings/QuickFilter bind `v-model="list"` (a frappe-ui
resource), mutate `list.params.*`, and pull field options from CRM endpoints
(`crm.api.doc.sort_options`, etc.) — coupling them to CRM's data shape and Views
concept. When extracting to `@framework/ui` we instead make each control a
**controlled component**: it owns one state slice via `v-model` (SortBy ↔ a
`Sort[]` array, with exported `parseOrderBy`/`serializeOrderBy` string helpers),
takes a `doctype`, derives its **Field Options** client-side from the existing
`useDoctypeMeta` (via pure, frappe-ui-free helpers), emits changes, and leaves
fetching/persistence/default-handling (e.g. CRM's "`modified desc` = unsorted"
rule) to the host. Cross-control sync (Filter ↔ Quick Filter, resize ↔ column
width) is deferred to a shared composable introduced only once two controls
actually need it.

## Considered Options

- **Bind the CRM resource (status quo).** Rejected: drags CRM's data shape and
  Views concept into a shared library.
- **Host passes options + state explicitly (fully presentational).** Rejected as
  the default: every consumer would rebuild the field list; deriving from Meta is
  more plug-and-play and matches `useDoctypeLayout`.
- **Shared composable from day one.** Rejected for now: premature abstraction;
  build controlled, let the composable emerge when sync forces it.
