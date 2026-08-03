import { computed } from "vue";
import type { ComputedRef } from "vue";
import { useFilters } from "../Filter/useFilters";
import type { UseFilters } from "../Filter/useFilters";
import { useSort } from "../SortBy/useSort";
import type { UseSort } from "../SortBy/useSort";
import { useQuickFilter } from "../QuickFilter/useQuickFilter";
import type { UseQuickFilter } from "../QuickFilter/useQuickFilter";
import { useColumns } from "../ColumnSettings/useColumns";
import type {
  UseColumns,
  UseColumnsOptions,
} from "../ColumnSettings/useColumns";
import type { FilterCondition, FilterField } from "../Filter/types";
import type { Sort } from "../SortBy/types";
import type { Column } from "../ColumnSettings/types";

/**
 * A persistable snapshot of the whole view's customizable state — the single
 * contract for saving and loading a layout (a per-user preference or a named saved
 * view), so a host seeds and persists one object instead of poking each control's
 * ref individually.
 *
 * Each member is the control's own state shape, which is plain-JSON-serializable
 * and self-contained (filter conditions carry their own field Meta; quick-filter
 * fields are full FilterFields) — so a round-trip needs no Meta and is lossless.
 * It captures the *effective* columns / quick-filter fields (custom or the Meta
 * default), never the transient `customizing` edit-mode flag.
 */
export interface ListViewSnapshot {
  /** The shared filter conditions (Filter + QuickFilter SoT). */
  filters: FilterCondition[];
  /** The sort order. */
  sort: Sort[];
  /** The shown columns (order, labels, widths). */
  columns: Column[];
  /** The QuickFilter strip's surfaced fields, in display order. */
  quickFilterFields: FilterField[];
}

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
  /** The whole view's customizable state as one reactive, persistable object —
   *  the save half of the layout-persistence seam. The library owns no saving: a
   *  host persists by watching this (`watch(view.snapshot, save)`) and decides
   *  *when* and *where* (ADR-0007). */
  snapshot: ComputedRef<ListViewSnapshot>;
  /** Seed the view from a (possibly partial) snapshot — the load half. Only the
   *  members present are applied, each over its own control's state, so a host can
   *  restore just the parts it persisted. */
  restore: (snapshot: Partial<ListViewSnapshot>) => void;
}

/** Host options threaded into the composed controls. Currently just the synthetic
 *  column declarations (ADR-0033), passed to `useColumns`. */
export interface UseListViewOptions extends UseColumnsOptions {}

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
export function useListView(
  doctype: string,
  options: UseListViewOptions = {}
): UseListView {
  const filters = useFilters();
  const sort = useSort();
  const quickFilter = useQuickFilter(doctype);
  const columns = useColumns(doctype, { synthetic: options.synthetic });

  // Reads the *effective* state off each control (the writable computeds resolve
  // custom-or-default), capturing live references — safe because every control
  // updates its array immutably (reassigns, never mutates in place), so a stored
  // snapshot can't change underneath a later restore.
  const snapshot = computed<ListViewSnapshot>(() => ({
    filters: filters.conditions.value,
    sort: sort.by.value,
    columns: columns.shown.value,
    quickFilterFields: quickFilter.fields.value,
  }));

  // Applies only the members present, each over its own control's ref — a partial
  // snapshot restores just those parts and leaves the rest at their defaults.
  const restore = (snapshot: Partial<ListViewSnapshot>) => {
    if (snapshot.filters) filters.conditions.value = snapshot.filters;
    if (snapshot.sort) sort.by.value = snapshot.sort;
    if (snapshot.columns) columns.shown.value = snapshot.columns;
    if (snapshot.quickFilterFields)
      quickFilter.fields.value = snapshot.quickFilterFields;
  };

  return { filters, sort, quickFilter, columns, snapshot, restore };
}
