import type { ListCell } from "@/contributions/types";
import type { ActFields } from "@/acts/dispatcher";
import type { PageApi, SurfaceItem, SurfaceVerbs } from "@/pageEngine/types";
import { ACT_KEYS } from "@/pageEngine/types";
import type { FilterCondition } from "@framework/ui/Filter";
import type { Sort } from "@framework/ui/SortBy";
import type { Ref } from "vue";

export type ListRow = Record<string, any>;

/** What the list page reads of the view it shows; the list's `View` fits it. */
export interface ListPageView {
  doctype: string;
  key: string;
  type: string;
  filters: Ref<FilterCondition[]>;
  sort: Ref<Sort[]>;
}

/** The bulk bar's More groups a built-in can sit in; a script's item is an app action, in none of them. */
export type BulkGroup = "workflow" | "collaborate" | "output" | "danger";

/** One item of `controls` or `bulkActions`; a built-in may draw itself and have no `run`. */
export interface ListPageAction extends SurfaceItem, ActFields<ListPageApi> {
  run?: (page: ListPageApi, value?: unknown) => unknown;
  /** Host side, set by a built-in only: where the bulk bar groups it in More. */
  group?: BulkGroup;
  /** Host side, set by a built-in only: the bulk bar draws it as a button. */
  button?: boolean;
  /** Host side, set by a built-in only: it is no bulk run, so the cap does not disable it. */
  uncapped?: boolean;
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
  /** The row fields a `badge` function reads besides the column's own; the list query fetches them. */
  fields?: string[];
}

export interface ListPageApi extends PageApi {
  controls: SurfaceVerbs<ListPageAction>;
  columns: SurfaceVerbs<ListPageColumn>;
  bulkActions: SurfaceVerbs<ListPageAction>;
  rowActions: SurfaceVerbs<ListRowAction>;
  /** The view on screen: its key and type. */
  view: { key: string; type: string };
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
export const COLUMN_KEYS: readonly string[] = ["name", "label", "width", "icons", "badge", "icon", "format", "switch", "fields"];

/** The row fields the columns' badge functions read, for the list query. */
export function columnFields(columns: ListPageColumn[]): string[] {
  return columns.flatMap((column) => (Array.isArray(column.fields) ? column.fields.filter((name) => typeof name === "string") : []));
}

/** The row fields the row actions read, for the list query. */
export function rowActionFields(actions: ListRowAction[]): string[] {
  return actions.flatMap((action) => action.fields ?? []);
}
