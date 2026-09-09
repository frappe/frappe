import { computed, ref, toValue } from "vue";
import type {
  ComputedRef,
  MaybeRefOrGetter,
  Ref,
  WritableComputedRef,
} from "vue";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import {
  serializeColumns,
  applyColumnWidth,
  clearColumnWidth,
  dropOrphanedSyntheticColumns,
} from "./columns";
import { getDefaultColumns, foldSyntheticColumns } from "./getDefaultColumns";
import type { Column, SyntheticColumn, WireColumn } from "./types";

export interface UseColumnsOptions {
  /** Host-declared synthetic columns (ADR-0033) — columns not resolved from Meta.
   *  Folded into the default `shown` at their `place` anchor, wired from their own
   *  render metadata, and offered back by the picker. Default: none (byte-identical).
   *  A `MaybeRefOrGetter` so a host whose declarations resolve asynchronously (e.g. the
   *  Record indicator, which rides a live field-meta fetch) can pass a computed and have
   *  the fold recompute when it arrives — plain arrays work unchanged. */
  synthetic?: MaybeRefOrGetter<SyntheticColumn[]>;
}

export interface UseColumns {
  /** The list's shown columns (order = display order, `width` = the resize slice).
   *  Defaults to the doctype's `in_list_view` fields (from Meta) until customized.
   *  The single source of truth ColumnSettings `v-model`s and the table's
   *  drag-resize writes back into — both bind this one ref, so they stay in sync
   *  with no cross-control events (ADR-0006). */
  shown: WritableComputedRef<Column[]>;
  /** Whether `shown` has been customized away from the Meta defaults — a Reset
   *  trigger reads this to show itself only when there is something to undo. */
  isCustomized: Ref<boolean>;
  /** Restore `shown` to the Meta-derived defaults (clears the customization, so the
   *  writable computed falls back to `getDefaultColumns`). ColumnSettings emits
   *  `@reset` to this; defaults live here, not in the controlled popover (ADR-0006). */
  reset: () => void;
  /** The frappe-ui `ListView` render columns (`serializeColumns`): the table binds
   *  these for headers + grid tracks, with `align`/`type`/`options` derived from Meta. */
  wire: Ref<WireColumn[]>;
  /** The resolved host-declared synthetic columns (ADR-0033), so a host can bind
   *  ColumnSettings' `:synthetic` prop (its picker union) from the same place it reads
   *  `shown` — one source, threaded from `useListView`. A `ComputedRef` so it tracks a
   *  reactive/async declaration source. */
  synthetic: ComputedRef<SyntheticColumn[]>;
  /** Write a resized column's width back into `shown` by `fieldname` (the
   *  resize→settings half of the sync). The `save` flag a host might debounce on is
   *  the host's concern and ignored here. */
  setWidth: (fieldname: string, width: string) => void;
  /** Drop a column's fixed `width` so it flexes to fill again (the reset half of the
   *  resize story). A host wires this to a double-click on the header resizer; with
   *  no stored width, `serializeColumns` falls the column back to an `fr`. */
  resetWidth: (fieldname: string) => void;
}

/**
 * Owns the shown `Column[]` (the ColumnSettings ↔ table-resize SoT, ADR-0006), its
 * Meta-derived defaults / reset, the wire render columns, and the resize writes.
 * Reads Meta itself (cached per doctype) so it's self-contained.
 *
 * `doctype` is taken by value: the Shell remounts the controls via `:key="doctype"`
 * and Meta is cached per doctype string, so reconstructing on a switch is cheap.
 */
export function useColumns(
  doctype: string,
  options: UseColumnsOptions = {}
): UseColumns {
  const { meta } = useDoctypeMeta(doctype);
  // Resolved reactively so an async declaration source (the indicator rides a live
  // field-meta fetch) folds in the moment it arrives, like the Meta-derived defaults do.
  const synthetic = computed<SyntheticColumn[]>(
    () => toValue(options.synthetic) ?? []
  );

  // `null` ⇒ "use the Meta-derived default"; a value ⇒ customized. The default
  // tracks Meta as it loads, yet the first write (a ColumnSettings edit or a resize)
  // sticks — no seed watch needed. Synthetic declarations fold into the default seed
  // only (ADR-0033); once customized, the persisted layout carries them. A customized
  // layout is scrubbed of orphaned synthetic keys on read (`dropOrphanedSyntheticColumns`):
  // a declaration can be removed after the user customized, leaving a `_`-prefixed column
  // that names no docfield and would error `get_list` — dropping it keeps the layout valid
  // while a re-declared key simply reappears.
  const customColumns = ref<Column[] | null>(null);
  const shown = computed<Column[]>({
    get: () =>
      customColumns.value
        ? dropOrphanedSyntheticColumns(customColumns.value, synthetic.value)
        : foldSyntheticColumns(
            getDefaultColumns(
              meta.value?.fields ?? [],
              meta.value?.title_field
            ),
            synthetic.value
          ),
    set: (value) => {
      customColumns.value = value;
    },
  });

  const isCustomized = computed(() => customColumns.value !== null);
  const reset = () => {
    customColumns.value = null;
  };

  const wire = computed(() =>
    serializeColumns(shown.value, meta.value?.fields ?? [], synthetic.value)
  );

  // A drag in the frappe-ui header emits `{ key, width }`; writing it back into
  // `shown` is what surfaces the new width in ColumnSettings.
  const setWidth = (fieldname: string, width: string) => {
    shown.value = applyColumnWidth(shown.value, fieldname, width);
  };

  // The reset half of the resize story: drop a column's fixed width so it flexes to
  // fill again. The host wires this to a double-click on the header resizer.
  const resetWidth = (fieldname: string) => {
    shown.value = clearColumnWidth(shown.value, fieldname);
  };

  return { shown, isCustomized, reset, wire, synthetic, setWidth, resetWidth };
}
