// GroupBy — the controlled, meta-driven group-by control, the table that shows one
// row per group, and their pure helpers. The control and table never fetch: a host
// either opts into `useGroupByData` for the rows and paging, or runs the control's
// model through `serializeGroupBy` itself. Field Options are derived from Meta.
export { default as GroupBy } from "./GroupBy.vue";
export { default as GroupByTable } from "./GroupByTable.vue";
export {
  AGGREGATE_FUNCTIONS,
  aggregateKey,
  columnId,
  effectiveSort,
  findGroupByField,
  getAggregateFields,
  getGroupByFields,
  parseGroupBy,
  serializeGroupBy,
  serializeGroupByTotals,
} from "./groupBy";
export { useGroupByData } from "./useGroupByData";
export type { UseGroupByData } from "./useGroupByData";
export type {
  Aggregate,
  AggregateFunction,
  GroupByColumn,
  GroupByField,
  GroupByProps,
  GroupBySettings,
  GroupByTableProps,
} from "./types";
