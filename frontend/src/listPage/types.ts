import type { ListCell } from "@/contributions/types";
import type { ActFields } from "@/acts/dispatcher";
import type { PageApi, SurfaceItem, SurfaceVerbs } from "@/pageEngine/types";
import { ACT_KEYS } from "@/pageEngine/types";
import type { FilterCondition } from "@framework/ui/Filter";
import type { Sort } from "@framework/ui/SortBy";
import type { View } from "@/list/view";

export type ListRow = Record<string, any>;

/** One item of `controls` or `bulkActions`; a built-in may draw itself and have no `run`. */
export interface ListPageAction extends SurfaceItem, ActFields<ListPageApi> {
  run?: (page: ListPageApi, value?: unknown) => unknown;
}

/** One row action: `run` and `when` get the row as `value`; `fields` names the columns it reads off the row. */
export interface ListRowAction extends SurfaceItem {
  run: (page: ListPageApi, row: ListRow) => unknown;
  when?: (page: ListPageApi, row: ListRow) => boolean;
  right?: string;
  fields?: string[];
}

/** One column of the List view; it carries how its cells draw. */
export interface ListPageColumn extends SurfaceItem, ListCell {
  width?: string;
}

export interface ListPageApi extends PageApi {
  controls: SurfaceVerbs<ListPageAction>;
  columns: SurfaceVerbs<ListPageColumn>;
  bulkActions: SurfaceVerbs<ListPageAction>;
  rowActions: SurfaceVerbs<ListRowAction>;
  /** The view on screen: its key and type. */
  view: Pick<View, "key" | "type">;
  /** The rows loaded now; read only. Not the record page's `page.rows(parentfield)`. */
  readonly rows: readonly ListRow[];
  /** The names of the selected rows; read only. */
  readonly selection: readonly string[];
  /** Setting them reloads the rows. */
  filters: FilterCondition[];
  sort: Sort[];
  reload(): void;
}

export const ACTION_KEYS: readonly string[] = ["name", "label", "icon", "run", ...ACT_KEYS];
export const ROW_ACTION_KEYS: readonly string[] = ["name", "label", "icon", "run", "when", "right", "fields"];
export const COLUMN_KEYS: readonly string[] = ["name", "label", "width", "icons", "badge", "icon", "format", "switch"];
