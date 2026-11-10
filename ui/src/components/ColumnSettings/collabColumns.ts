/** The options both pickers add beside a doctype's own fields. */
export interface ColumnMeta {
  is_submittable?: 0 | 1;
  is_virtual?: 0 | 1;
}

export const DOCSTATUS_COLUMN = { label: "Document Status", fieldname: "docstatus" };

/** Desk v1's collaboration columns. `_favourite` is no table column: the list read reports it
 *  as a part. A virtual doctype has no table, so none of these can be read from it. */
const COLLAB_COLUMNS: ReadonlyArray<{ label: string; fieldname: string }> = [
  { label: "Assigned To", fieldname: "_assign" },
  { label: "Favourite", fieldname: "_favourite" },
  { label: "Tags", fieldname: "_user_tags" },
  { label: "Comments", fieldname: "_comments" },
  { label: "Liked By", fieldname: "_liked_by" },
];

export function collabColumns(meta: ColumnMeta = {}): { label: string; fieldname: string }[] {
  if (meta.is_virtual) return [];
  const status = meta.is_submittable ? [DOCSTATUS_COLUMN] : [];
  return [...COLLAB_COLUMNS, ...status];
}

/** Only a real table column orders a list: the rest are cache columns, or a part of the read. */
const UNSORTABLE = new Set(COLLAB_COLUMNS.map((column) => column.fieldname));

export const isSortableColumn = (fieldname: string): boolean => !UNSORTABLE.has(fieldname);
