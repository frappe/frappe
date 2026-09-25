/**
 * Resolve a sibling field's value in Frappe desk precedence: row → doc → parent.
 * First non-blank value wins; all blank → `undefined`. Keeps context-dependent
 * fieldtypes (Currency, Dynamic Link, …) in sync between grid cell and row dialog,
 * which surface the same records differently but both collapse to row-data → parent.
 */
export interface RecordContext {
  /** The child-table row's values, when the field renders as a grid cell. */
  row?: Record<string, any> | null;
  /** The doc the field lives on (parent doc for a grid cell, row clone in the dialog). */
  doc?: Record<string, any> | null;
  /** The parent doc; consulted last, so a row-local sibling always wins. */
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
