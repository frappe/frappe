import { computed, ref, watch } from "vue";
import type { Ref } from "vue";
import type { ListRowData } from "./types";

export type SelectAllState = "none" | "some" | "all";

/**
 * The checkbox column's logic: one row toggles, the header toggles every shown row, and a range runs
 * from the last row toggled (the anchor) to another.
 */
export function useRowSelection(
  selection: Ref<string[]>,
  rows: Ref<ListRowData[]>,
  rowKey: Ref<string>
) {
  const allKeys = computed(() =>
    rows.value.map((row) => String(row[rowKey.value]))
  );

  const selected = computed(() => new Set(selection.value));

  const selectAllState = computed<SelectAllState>(() => {
    const selected = allKeys.value.filter((key) =>
      isSelected(key)
    ).length;
    // A selected row that a filter hides still counts, so the header never reads empty beside "N selected".
    if (!selected) return selection.value.length ? "some" : "none";
    return selected === allKeys.value.length ? "all" : "some";
  });

  function isSelected(value: string) {
    return selected.value.has(value);
  }

  // The row a range starts from; an emptied selection forgets it.
  const anchor = ref<string | null>(null);
  watch(
    () => selection.value.length,
    (length) => {
      if (!length) anchor.value = null;
    },
    { flush: "sync" }
  );

  /** A range toggle gives every row between the anchor and `value` the state `value` takes. */
  function toggle(value: string, range = false) {
    const selecting = !isSelected(value);
    const between = range ? rowsBetween(anchor.value, value) : [value];
    setRows(between, selecting);
    anchor.value = selection.value.length ? value : null;
  }

  /** Selects the rows from the anchor to `value`; with no anchor, `value` alone. */
  function extendTo(value: string) {
    setRows(rowsBetween(anchor.value, value), true);
    anchor.value = value;
  }

  function rowsBetween(from: string | null, to: string) {
    const start = from === null ? -1 : allKeys.value.indexOf(from);
    const end = allKeys.value.indexOf(to);
    if (start < 0 || end < 0) return [to];
    return allKeys.value.slice(Math.min(start, end), Math.max(start, end) + 1);
  }

  function setRows(keys: string[], selecting: boolean) {
    const changed = new Set(keys);
    const rest = selection.value.filter((key) => !changed.has(key));
    selection.value = selecting ? [...rest, ...keys] : rest;
  }

  // Selected rows outside the shown set stay selected; only the shown rows clear.
  function toggleSelectAll() {
    if (selectAllState.value === "all") {
      const shown = new Set(allKeys.value);
      selection.value = selection.value.filter((key) => !shown.has(key));
    } else {
      selection.value = [...new Set([...selection.value, ...allKeys.value])];
    }
  }

  return { selectAllState, isSelected, toggle, extendTo, toggleSelectAll };
}
