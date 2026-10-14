// GroupBy — the controlled, meta-driven group-by control, the table that shows one
// row per group, and their pure helpers. The host owns fetching: it passes the
// control's model through `serializeGroupBy` to `frappe.client.get_list` and hands
// the rows to `GroupByTable`. Field Options are derived from doctype Meta.
export { default as GroupBy } from "./GroupBy.vue";
export { default as GroupByTable } from "./GroupByTable.vue";
export {
  AGGREGATE_FUNCTIONS,
  aggregateKey,
  findGroupByField,
  getAggregateFields,
  getGroupByFields,
  isCompleteAggregate,
  parseGroupBy,
  serializeGroupBy,
} from "./groupBy";
export type {
  Aggregate,
  AggregateFunction,
  GroupByColumn,
  GroupByField,
  GroupByProps,
  GroupBySettings,
  GroupByTableProps,
} from "./types";
