import type { RouteLocationRaw } from "vue-router";
import type { Column } from "../../components/ColumnSettings/types";

/** A shown column: the Column Settings shape plus the alignment a host derives from Meta. */
export interface ListColumn extends Column {
  align?: "left" | "right";
}

export type ListRowData = Record<string, unknown>;

export interface ListProps {
  columns?: ListColumn[];
  rows?: ListRowData[];
  /** The row property that identifies it, for the selection and the render key. */
  rowKey?: string;
  loading?: boolean;
  /** Fixed row height in px; virtual rows need it. */
  rowHeight?: number;
  /** The route a row opens; with it, every row renders as a link. */
  rowLink?: (row: ListRowData) => RouteLocationRaw;
  /** Where the checkbox and the last cell's text land, as a CSS length; the row bleeds past it. */
  gutter?: string;
}

/** A drag-resize result: the column and the fixed width it now has. */
export interface ColumnResize {
  fieldname: string;
  width: string;
}

export interface BulkAction {
  label: string;
  theme?: "gray" | "blue" | "green" | "red";
  onClick: (selection: string[]) => void;
}
