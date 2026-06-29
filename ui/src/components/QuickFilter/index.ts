// QuickFilter — the controlled, meta-driven quick-filter control plus its pure,
// frappe-ui-free projection helpers. It binds the SAME `Filter[]` the Filter
// control does (the SoT `useListView` owns), so the two stay in sync with no
// event plumbing. Surfaced fields default to the doctype's `in_standard_filter`
// fields via `getQuickFilterFields`; the projection is by canonical operator.
export { default as QuickFilter } from "./QuickFilter.vue";
export { getQuickFilterFields } from "./getQuickFilterFields";
export {
  quickFilterOperator,
  quickFilterOperators,
  hasOperatorToggle,
  quickValue,
  quickOperator,
  applyQuick,
} from "./quickFilters";
