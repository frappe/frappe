import { useFilters } from "../Filter/useFilters";
import type { UseFilters } from "../Filter/useFilters";
import { useSort } from "../SortBy/useSort";
import type { UseSort } from "../SortBy/useSort";
import { useQuickFilter } from "../QuickFilter/useQuickFilter";
import type { UseQuickFilter } from "../QuickFilter/useQuickFilter";
import { useColumns } from "../ColumnSettings/useColumns";
import type { UseColumns } from "../ColumnSettings/useColumns";

export interface UseListView {
  /** The shared filter conditions (`conditions`, the SoT both Filter and QuickFilter
   *  bind) and the wire filter list a host fetches with (`wire`). */
  filters: UseFilters;
  /** The sort order (`by`) and the `order_by` string a host fetches with (`orderBy`). */
  sort: UseSort;
  /** The QuickFilter strip: surfaced `fields`, its `customizing` edit-mode, and
   *  whether the doctype offers anything to customize (`canCustomize`). */
  quickFilter: UseQuickFilter;
  /** The shown columns (`shown`, the ColumnSettings ↔ table-resize SoT), the wire
   *  render columns (`wire`), customization state (`isCustomized` / `reset`), and the
   *  resize writes (`setWidth` / `resetWidth`). */
  columns: UseColumns;
}

/**
 * The composite List View's state owner — the shared composable ADR-0001 deferred
 * until two controls needed to share state (Filter + QuickFilter are that moment,
 * ADR-0005; ColumnSettings + table-resize are the second, ADR-0006).
 *
 * It owns no state itself: each concern lives in its own co-located composable
 * (`useFilters`, `useSort`, `useQuickFilter`, `useColumns`), and this composes them
 * into one namespaced surface so a host can tell at a glance which member drives
 * which control. Each sub-composable reads Meta itself (cached per doctype), so the
 * grouping costs nothing.
 *
 * `doctype` is taken by value, not a reactive ref: the Shell remounts the controls
 * via `:key="doctype"` and `useDoctypeMeta` is cached per doctype string, so
 * reconstructing `useListView` on a doctype switch is cheap and needs no internal
 * reset watch.
 */
export function useListView(doctype: string): UseListView {
  return {
    filters: useFilters(),
    sort: useSort(),
    quickFilter: useQuickFilter(doctype),
    columns: useColumns(doctype),
  };
}
