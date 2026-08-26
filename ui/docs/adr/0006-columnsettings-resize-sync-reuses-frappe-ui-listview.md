# Column Settings ↔ resize sync via a shared `columns` ref; table chrome reuses frappe-ui's ListView

The **Column Settings** control and the list-table's drag-resize both edit the *same*
column's width, so — as with Filter ↔ Quick Filter ([ADR-0005](0005-quickfilter-projects-over-shared-filter-list.md)) —
they share one state slice rather than syncing via events: `useListView` owns
`columns: Ref<Column[]>`, ColumnSettings `v-model`s it, and the resize handler writes
the new width straight back into the matching entry by `fieldname`. Both bind one ref,
so the sync is automatic. The resize handler lives in the **`ListView` composite**, not
in ColumnSettings — resize is a table behaviour and the shared state already lives
there, leaving ColumnSettings a focused, controlled popover. The composite's table
chrome **reuses frappe-ui's `ListView`/`ListHeader`/`ListHeaderItem`** (the same
components CRM renders) rather than a hand-rolled resizable header: this gets the drag
math (50px min, px-string width), grid layout, and pixel-parity for free. A column's
`width` is a CSS string (`"11rem"`/`"120px"`); `align`/`type`/`options` are derived
from **Meta** at render/serialize time, never stored on `Column`.

## Considered Options

- **Port CRM's resize drag math into a custom header.** Rejected: re-derives
  positioning frappe-ui already owns and risks pixel drift from CRM. `ui/CLAUDE.md`
  mandates reaching for the frappe-ui equivalent first.
- **Put the resize handler inside ColumnSettings.** Rejected: couples the popover
  control to table rendering; the composite already owns the shared `columns` and the
  table, so the handler belongs there.
- **Sync via emitted `columnWidthUpdated` events between control and table.** Rejected:
  the shared-ref pattern (ADR-0005) makes event plumbing unnecessary.

## Consequences

- Persistence is the host's job (ADR-0001): the control ignores frappe-ui's
  `save:false/true` debounce flag and just updates state live; a host that wants
  debounced saves watches `columns` itself.
- CRM's `rows` (fields-to-fetch) and reset / reset-to-defaults are **not** part of the
  control — they are host/story concerns, since they require saved/default state the
  controlled component does not hold.
