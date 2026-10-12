import { computed } from "vue";
import type { Ref } from "vue";
import type { ListRowData } from "./types";

export type SelectAllState = "none" | "some" | "all";

/** The checkbox column's logic: one row toggles, the header toggles every shown row. */
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
    if (!selected) return "none";
    return selected === allKeys.value.length ? "all" : "some";
  });

  function isSelected(value: string) {
    return selected.value.has(value);
  }

  function toggle(value: string) {
    selection.value = isSelected(value)
      ? selection.value.filter((key) => key !== value)
      : [...selection.value, value];
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

  return { selectAllState, isSelected, toggle, toggleSelectAll };
}
