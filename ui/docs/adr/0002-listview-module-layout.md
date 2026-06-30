# List View module layout: one module per control + a composite module

Each extracted control gets its own `@framework/ui` module folder (`SortBy/`,
`Filter/`, `ColumnSettings/`, `QuickFilter/`), mirroring `FileUpload/` and
`FormLayout/`: an `index.ts` with its own export subpath, the `.vue`, pure
helpers, and `stories/` + `tests/` subfolders holding an isolated demo and unit
tests. A separate **composite `ListView/` module** holds the combined "shell"
story now and grows into the shared composite (table, footer, selection banner,
`useListView` state composable). CRM mounts the shell on a temporary dev route
(it resolves `@framework/ui` via vite alias + `link:`) to chase pixel parity.

Controls reuse `frappe-ui` directly in `.vue` (Autocomplete, Popover, Button)
and lucide icon names; pure logic stays in frappe-ui-free `.ts` so it is unit
testable. The `fields/` value-input components (needed by Filter/QuickFilter,
not SortBy) may be lifted out of `FormLayout/` for shared use — deferred to the
Filter phase rather than moved pre-emptively.

## Considered Options

- **One `ListView/` module for all four controls.** Rejected in favor of
  per-control modules for isolation, at the cost of more files/exports.
- **Shell story in CRM or a top-level `stories/` dir.** Rejected: the shell will
  become real shared composite code, so it belongs in a library module.
