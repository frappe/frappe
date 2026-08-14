// Client-side identity for a child row that has no server `name` yet.

/**
 * Deliberately not a `name`: `frappe.client.save` sends the whole document and
 * `_init_child` treats a row that already carries a `name` as existing, so a
 * client-minted name makes the insert a silent no-op UPDATE.
 */
export const ROW_ID = "__row_id";

let minted = 0;

export function mintRowId(): string {
  return `row-${++minted}`;
}

/** The row's stable key, once it has one. */
export function rowKey(row: Record<string, any>): string | undefined {
  return row?.name ?? row?.[ROW_ID];
}

/** Fieldtypes whose value is rows: they commit through those, never themselves. */
const CHILD_TABLE_TYPES = new Set(["Table", "Table MultiSelect"]);

export function holdsChildRows(fieldtype: string): boolean {
  return CHILD_TABLE_TYPES.has(fieldtype);
}

/** Gives the row an id when it has neither a `name` nor one already. */
export function identify(row: Record<string, any>): Record<string, any> {
  if (!rowKey(row)) row[ROW_ID] = mintRowId();
  return row;
}
