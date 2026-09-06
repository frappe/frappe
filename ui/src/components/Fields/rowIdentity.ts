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

/**
 * The row's stable key, once it has one. A server name and a client id are
 * different kinds of identifier, so they get different keyspaces: `validate_name`
 * forbids only `<` and `>`, so a child doctype named by a field or a series can
 * legitimately produce a name equal to a minted id — and two rows sharing one
 * key read as one selection, and delete as one row.
 */
export function rowKey(row: Record<string, any>): string | undefined {
  if (row?.name) return `name:${row.name}`;
  const id = row?.[ROW_ID];
  return id ? `new:${id}` : undefined;
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
