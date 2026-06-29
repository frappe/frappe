import { computed, ref } from "vue";
import type { Ref, WritableComputedRef } from "vue";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { serializeFilters } from "../Filter/filters";
import type { WireFilters } from "../Filter/filters";
import type { FilterCondition, FilterField } from "../Filter";
import { serializeOrderBy } from "../SortBy/orderBy";
import type { Sort } from "../SortBy";
import { getQuickFilterFields } from "../QuickFilter/getQuickFilterFields";
import { getFilterableFields } from "../Filter/getFilterableFields";
import {
  serializeColumns,
  applyColumnWidth,
  clearColumnWidth,
} from "../ColumnSettings/columns";
import { getDefaultColumns } from "../ColumnSettings/getDefaultColumns";
import type { Column, WireColumn } from "../ColumnSettings/types";

export interface UseListView {
  /** The single source of truth for filter conditions — both the Filter and the
   *  QuickFilter controls `v-model` this same array, so they stay in sync with no
   *  cross-control events. */
  filters: Ref<FilterCondition[]>;
  /** The list's sort order; the SortBy control binds this. */
  sorts: Ref<Sort[]>;
  /** The list's shown columns (order = display order, `width` = the resize slice).
   *  Defaults to the doctype's `in_list_view` fields (from Meta) until customized —
   *  the column analog of `quickFilterFields` defaulting to `in_standard_filter`.
   *  The single source of truth ColumnSettings `v-model`s and the table's
   *  drag-resize writes back into — both bind this one ref, so they stay in sync
   *  with no cross-control events (ADR-0006, the column twin of Filter↔QuickFilter). */
  columns: WritableComputedRef<Column[]>;
  /** Whether `columns` has been customized away from the Meta defaults — a Reset
   *  trigger reads this to show itself only when there is something to undo. */
  isColumnsCustomized: Ref<boolean>;
  /** Restore `columns` to the Meta-derived defaults (clears the customization, so
   *  the writable computed falls back to `getDefaultColumns`). ColumnSettings emits
   *  `@reset` to this; defaults live here, not in the controlled popover (ADR-0006). */
  resetColumns: () => void;
  /** The fields surfaced as QuickFilter inputs. Defaults to the doctype's
   *  `in_standard_filter` fields (from Meta) until customized; a host may bind
   *  this (alongside QuickFilter's `v-model:fields`) to persist the choice. */
  quickFilterFields: WritableComputedRef<FilterField[]>;
  /** Whether the quick-filter strip is in customize (edit) mode. Owned here so a
   *  customize trigger can live anywhere — not just beside QuickFilter — and still
   *  drive its edit state. QuickFilter `v-model:customizing`s this. */
  customizing: Ref<boolean>;
  /** Whether the doctype offers any filterable field to surface — a trigger reads
   *  this to hide itself when there is nothing to customize. */
  canCustomize: Ref<boolean>;
  /** The Frappe wire filter list a host fetches with (`serializeFilters(filters)`). */
  wireFilters: Ref<WireFilters>;
  /** The Frappe `order_by` string a host fetches with (`serializeOrderBy(sorts)`). */
  orderBy: Ref<string>;
  /** The frappe-ui `ListView` render columns (`serializeColumns(columns, meta)`):
   *  the table binds these for headers + grid tracks, with `align`/`type`/`options`
   *  derived from Meta. */
  wireColumns: Ref<WireColumn[]>;
  /** The table's `columnWidthUpdated` handler — writes a resized column's width
   *  back into the shared `columns` ref by `fieldname` (the resize→settings half
   *  of the sync). The composite owns this, not ColumnSettings; the `save` flag a
   *  host might debounce on is the host's concern and ignored here. */
  setColumnWidth: (fieldname: string, width: string) => void;
  /** Drop a column's fixed `width` so it flexes to fill again (the reset half of
   *  the resize story). A host wires this to a double-click on the header resizer;
   *  with no stored width, `serializeColumns` falls the column back to an `fr`. */
  resetColumnWidth: (fieldname: string) => void;
}

/**
 * The composite List View's state owner — the shared composable ADR-0001
 * deferred until two controls needed to share state (Filter + QuickFilter are
 * that moment, ADR-0005; ColumnSettings + table-resize are the second, ADR-0006).
 * It owns the `Filter[]` SoT, `sorts`, the surfaced quick-filter fields, and the
 * shown `columns`, and exposes the `wireFilters` / `orderBy` / `wireColumns`
 * computeds a host fetches and renders with.
 *
 * `doctype` is taken by value, not a reactive ref: the Shell remounts the
 * controls via `:key="doctype"` and `useDoctypeMeta` is cached per doctype
 * string, so reconstructing `useListView` on a doctype switch is cheap and
 * needs no internal reset watch.
 */
export function useListView(doctype: string): UseListView {
  const { meta } = useDoctypeMeta(doctype);

  const filters = ref<FilterCondition[]>([]);
  const sorts = ref<Sort[]>([]);

  // `null` ⇒ "use the Meta-derived default"; a value ⇒ customized. Mirrors
  // `quickFilterFields`: the default tracks Meta as it loads, yet the first write
  // (a ColumnSettings edit or a resize) sticks — no seed watch needed.
  const customColumns = ref<Column[] | null>(null);
  const columns = computed<Column[]>({
    get: () =>
      customColumns.value ??
      getDefaultColumns(meta.value?.fields ?? [], meta.value?.title_field),
    set: (value) => {
      customColumns.value = value;
    },
  });

  // Reset is a host concern (ADR-0006): the controlled popover holds no defaults,
  // so clearing the customization here drops `columns` back to `getDefaultColumns`.
  const isColumnsCustomized = computed(() => customColumns.value !== null);
  const resetColumns = () => {
    customColumns.value = null;
  };

  // `null` ⇒ "use the Meta-derived default"; a value ⇒ the host/user customized
  // it. A writable computed so the default tracks Meta as it loads, yet a
  // customization (via `v-model:fields`) sticks — no seed watch needed.
  const customQuickFilterFields = ref<FilterField[] | null>(null);
  const quickFilterFields = computed<FilterField[]>({
    get: () =>
      customQuickFilterFields.value ??
      getQuickFilterFields(meta.value?.fields ?? [], doctype),
    set: (value) => {
      customQuickFilterFields.value = value;
    },
  });

  const customizing = ref(false);
  const canCustomize = computed(
    () => getFilterableFields(meta.value?.fields ?? [], doctype).length > 0
  );

  const wireFilters = computed(() => serializeFilters(filters.value));
  const orderBy = computed(() => serializeOrderBy(sorts.value));
  const wireColumns = computed(() =>
    serializeColumns(columns.value, meta.value?.fields ?? [])
  );

  // The resize handler lives here in the composite (ADR-0006): a drag in the
  // frappe-ui header emits `{ key, width }`, and writing it back into the shared
  // `columns` ref is what surfaces the new width in ColumnSettings.
  const setColumnWidth = (fieldname: string, width: string) => {
    columns.value = applyColumnWidth(columns.value, fieldname, width);
  };

  // The reset half of the resize story: drop a column's fixed width so it flexes
  // to fill again. The host wires this to a double-click on the header resizer.
  const resetColumnWidth = (fieldname: string) => {
    columns.value = clearColumnWidth(columns.value, fieldname);
  };

  return {
    filters,
    sorts,
    columns,
    isColumnsCustomized,
    resetColumns,
    quickFilterFields,
    customizing,
    canCustomize,
    wireFilters,
    orderBy,
    wireColumns,
    setColumnWidth,
    resetColumnWidth,
  };
}
