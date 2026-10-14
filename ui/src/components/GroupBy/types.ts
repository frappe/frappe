import type { Sort } from "../SortBy/types";

/** The SQL aggregate an **Aggregate** applies to each group. */
export type AggregateFunction = "count" | "sum" | "avg" | "min" | "max";

/** One summary column of a grouped list: a function, and for all but `count`
 *  the field it runs on. See CONTEXT.md ("Aggregate"). */
export type Aggregate =
  | { function: "count" }
  | { function: Exclude<AggregateFunction, "count">; fieldname: string };

/** An aggregate as the control's panel edits it, which may have no field yet. */
export interface AggregateDraft {
  function: AggregateFunction;
  fieldname?: string;
}

/** The control's state: the fields a list is grouped by, in order, and the
 *  aggregates shown for each group. `null` on the model means ungrouped. See
 *  CONTEXT.md ("Group By"). */
export interface GroupBySettings {
  fields: string[];
  aggregates: Aggregate[];
  /** Column widths the user dragged, by `columnId`; absent means auto. */
  widths?: Record<string, string>;
  /** The header sort, by `columnId`. Absent, or for a column no longer shown, the
   *  groups sort by the first aggregate, largest first (see `effectiveSort`). */
  sort?: Sort[];
  /** Whether a totals row shows under the groups. */
  showTotals?: boolean;
}

/** A field the control offers for grouping or aggregating, derived from Meta. */
export interface GroupByField {
  label: string;
  value: string;
  fieldname: string;
  fieldtype: string;
  options?: string;
}

/** Props for `<GroupBy>`. The grouping itself is the `v-model` (`GroupBySettings | null`). */
export interface GroupByProps {
  /** Doctype whose Meta drives the groupable and aggregatable fields. */
  doctype: string;
  /** Show only the icon on the trigger. */
  hideLabel?: boolean;
  /** Which edge of the button the popover lines up with. Defaults to `end`. */
  align?: "start" | "end";
}

/** Props for `<GroupByTable>`. The host fetches `rows` with `serializeGroupBy`. */
export interface GroupByTableProps {
  doctype: string;
  groupBy: GroupBySettings;
  /** The grouped query's result rows, as `frappe.client.get_list` returns them. */
  rows: Record<string, unknown>[];
  /** The totals row, aggregate values by `aggregateKey`; shown when `showTotals` is on. */
  totals?: Record<string, unknown> | null;
  loading?: boolean;
  /** Fixed row height in px. Defaults to 40, the List module's own. */
  rowHeight?: number;
}

/** One column of `<GroupByTable>`, as its `#cell` slot receives it. */
export interface GroupByColumn {
  /** The row key: a fieldname, or an aggregate's `aggregateKey`. */
  key: string;
  /** The id its width and sort are saved under, stable when other columns come and go. */
  id: string;
  label: string;
  /** A grouped field, or an aggregate's value. */
  kind: "group" | "aggregate";
  /** Follows `kind`: grouped values read from the left, aggregates from the right. */
  align: "left" | "right";
  /** The grouped field's fieldtype, or the aggregated field's. */
  fieldtype?: string;
  options?: string;
}
