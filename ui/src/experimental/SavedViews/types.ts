import type { WireFilters } from "../../components/Filter/filters";
import type { WireColumn } from "../../components/ColumnSettings/types";

export interface SavedView {
  name: string | number;
  label: string;
  icon?: string;
  reference_doctype: string;
  type: SavedViewType;
  user?: string;
  is_default?: 0 | 1;
  filters?: string | WireFilters | null;
  order_by?: string | null;
  columns?: string | WireColumn[] | null;
  rows?: string | string[] | null;
  group_by_field?: string | null;
  column_field?: string | null;
  title_field?: string | null;
  kanban_columns?: string | unknown[] | null;
  kanban_fields?: string | string[] | null;
  hidden?: 0 | 1;
}

export type SavedViewType = "list" | "group_by" | "kanban";

export interface ViewFormValues {
  label: string;
  icon: string;
  shared: boolean;
}
