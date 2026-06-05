/**
 * Minimal shape `Grid` needs to render a column's header and key its cells.
 * Richer column objects (e.g. FormLayout's `FieldMeta`) satisfy this
 * structurally, so callers pass their own type through `Grid`'s generic and get
 * it back, fully typed, in the `#cell` slot.
 */
export interface GridColumn {
  fieldname: string
  label?: string
  reqd?: boolean
}

export type GridEmits = {
  /**
   * A row was added, deleted, reordered, or a cell committed (via the slot's
   * `commit`). Carries the new rows array — the intentful "the grid changed"
   * signal, distinct from the live `v-model` sync (the slot's `update`).
   */
  change: [rows: Record<string, any>[]]
}

/** Scoped-slot payload for rendering/editing a single cell. */
export interface GridCellSlotProps<T extends GridColumn = GridColumn> {
  row: Record<string, any>
  column: T
  index: number
  /** Current cell value (`row[column.fieldname]`). */
  value: any
  /** Live cell write — keeps the value reactive while editing (no `change`). */
  update: (value: any) => void
  /** Commit the cell — writes the value and emits `change`. */
  commit: (value: any) => void
}
