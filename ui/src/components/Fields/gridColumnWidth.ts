import type { FieldNode } from "../FormLayout/types";

/** Desk v1's map from a DocField's `columns` to a grid column's px width (grid.js). */
const COLUMNS_PX: Record<number, number> = {
  1: 60,
  2: 100,
  3: 140,
  4: 200,
  5: 250,
  6: 300,
  7: 350,
  8: 400,
  9: 450,
  10: 500,
  11: 550,
  12: 600,
};

/** Desk v1's width for a column whose `columns` is empty (Auto). */
const FIELDTYPE_PX: Record<string, number> = {
  Text: 200,
  "Small Text": 200,
  "Long Text": 200,
  Check: 60,
  Int: 100,
  Float: 100,
  Currency: 100,
  Percent: 100,
};
const DEFAULT_PX = 140;

/** A `Table` grid column's width in px: its `columns`, else its fieldtype's default. */
export function gridColumnWidth(field: Pick<FieldNode, "fieldtype" | "gridColumns">): number {
  return COLUMNS_PX[field.gridColumns ?? 0] ?? FIELDTYPE_PX[field.fieldtype] ?? DEFAULT_PX;
}
