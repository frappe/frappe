/**
 * Minimal shape `Grid` needs to render a column's header and key its cells.
 * Richer column objects (e.g. FormLayout's `FieldMeta`) satisfy this
 * structurally, so callers pass their own type through `Grid`'s generic and get
 * it back, fully typed, in the `#cell` slot.
 */
export interface GridColumn {
  fieldname: string;
  label?: string;
  reqd?: boolean;
  /**
   * Horizontal alignment for this column's cells *and* its header label, so the
   * two always agree. Defaults to left. Consumers set `"right"` for numeric
   * columns (e.g. `TableField` for Int/Float/Currency/Percent), matching how
   * Frappe desk right-aligns numbers in the grid.
   */
  align?: "left" | "right" | "center";
  /**
   * Initial track width in px, e.g. set from layout/meta. Omit for a flexible
   * column that shares leftover space (`1fr`). Drag-resizing the column's right
   * edge overrides this at runtime.
   */
  width?: number;
}

/** Validation error shown below the grid: a message string, or an `Error` with `messages[]`. */
export interface GridError extends Error {
  messages?: string[];
}

/** Props for `<Grid>`. The rows array is a separate `v-model`. */
export interface GridProps {
  /** Columns to render, in order. */
  columns: GridColumn[];
  /** Disable structural actions (add/delete/reorder/select) and render read-only. */
  disabled?: boolean;
  /** Optional heading shown above the grid. */
  label?: string;
  /** Helper text rendered below the grid. Hidden while an error is shown. */
  description?: string;
  /** Validation error below the grid: a string, or an `Error` with `messages[]`. */
  error?: string | GridError;
  /** Renders a `*` next to the label. */
  required?: boolean;
}

export type GridEmits = {
  /**
   * A row was added, deleted, reordered, or a cell committed (via the slot's
   * `commit`). Carries the new rows array — the intentful "the grid changed"
   * signal, distinct from the live `v-model` sync (the slot's `update`).
   */
  change: [rows: Record<string, any>[]];
  /**
   * The user clicked a row's edit action (last column). Carries the row and its
   * index. `Grid` stays oblivious to *how* a row is edited — the consumer (e.g.
   * `TableField`) opens a dialog and renders the row however it likes.
   */
  edit: [payload: { row: Record<string, any>; index: number }];
};

/** Scoped-slot payload for rendering/editing a single cell. */
export interface GridCellSlotProps<T extends GridColumn = GridColumn> {
  row: Record<string, any>;
  column: T;
  index: number;
  /** Current cell value (`row[column.fieldname]`). */
  value: any;
  /** Live cell write — keeps the value reactive while editing (no `change`). */
  update: (value: any) => void;
  /** Commit the cell — writes the value and emits `change`. */
  commit: (value: any) => void;
}

export interface GridSlots<T extends GridColumn = GridColumn> {
  /** Render/edit one cell. Falls back to plain text when not provided. */
  cell?: (props: GridCellSlotProps<T>) => any;
}
