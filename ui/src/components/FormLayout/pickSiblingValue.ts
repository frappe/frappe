/**
 * Resolve a sibling field's value for a child-table row, across the records a
 * row's field can see, in Frappe desk's precedence: the row's own column first,
 * then the doc the field lives on, then the parent doc. The first *present*
 * (non-blank) value wins; all blank → `undefined`.
 *
 * This is the single source of truth for "which record a row's field reads a
 * sibling from", so every context-dependent fieldtype (Currency's currency
 * code, Dynamic Link's target doctype, …) stays in sync between the grid cell
 * and the row-edit dialog — the two differ only in *how* the same records reach
 * the field:
 *
 * - **Grid cell**: `row` = the child row (prop), `doc` = the parent doc (the
 *   injected `DocKey`), `parentDoc` = the parent doc again (provided by
 *   `TableField`).
 * - **Row dialog**: `row` is absent, `doc` = the row clone (the nested
 *   `FormLayout` shadows `DocKey`), `parentDoc` = the parent doc.
 *
 * Either way the precedence collapses to *row-data → parent*, so both paths
 * resolve identically.
 */
export interface RecordContext {
  /** The child-table row's values, when the field renders as a grid cell. */
  row?: Record<string, any> | null;
  /** The doc the field lives on — the parent doc for a grid cell, the row clone
   *  inside the row dialog. */
  doc?: Record<string, any> | null;
  /** The parent doc, for a row field whose sibling reference names a parent
   *  field. Consulted last, so a row-local sibling always wins. */
  parentDoc?: Record<string, any> | null;
}

/** A blank (`undefined`/`null`/`''`) value defers to the next record. */
function present(value: unknown): boolean {
  return value !== undefined && value !== null && value !== "";
}

export function pickSiblingValue(records: RecordContext, field: string): any {
  const fromRow = records.row?.[field];
  if (present(fromRow)) return fromRow;
  const fromDoc = records.doc?.[field];
  if (present(fromDoc)) return fromDoc;
  return records.parentDoc?.[field];
}
