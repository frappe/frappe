import { computed, getCurrentInstance, inject } from "vue";
import type { WritableComputedRef } from "vue";
import { CommitKey, NO_COMMIT } from "../Fields/types";
import { identify, rowKey } from "../Fields/rowIdentity";

/**
 * Bridge a `Table MultiSelect` field's stored value (an array of child rows,
 * each holding the picked record under the child table's link fieldname) to the
 * flat `string[]` of link values the `TableMultiSelect` control speaks.
 *
 * On write it reuses the existing row object for values that stay selected (so
 * `doctype`/`name` and any other cells survive) and mints `{ [linkFieldname]:
 * value }` for new ones — then emits both `update:modelValue` and `change`
 * (a selection is a commit for a picker). Shared by the lib field and any app
 * override field so neither re-implements the bridge.
 */
/** The emit shape both field wrappers have (a subset of `FieldComponentEmits`).
 *  Overloaded form, not a union arg, so Vue's `defineEmits()` value is assignable. */
type ChildRowEmit = {
  (event: "update:modelValue", value: unknown): void;
  (event: "change", value: unknown): void;
};

export function useChildRowModel(
  modelValue: () => unknown,
  linkFieldname: () => string,
  emit: ChildRowEmit,
  parentfield?: () => string
): WritableComputedRef<string[]> {
  const rows = computed<Record<string, any>[]>(() => {
    const v = modelValue();
    return Array.isArray(v) ? v : [];
  });

  // The second place in the stack that creates a child row, so it mints
  // identity and signals the structural edit the same way the grid does.
  const commit = getCurrentInstance() ? inject(CommitKey, NO_COMMIT) : NO_COMMIT;

  function signal(row: Record<string, any>, change: "add" | "remove") {
    const table = parentfield?.();
    if (!table) return;
    commit.rowChanged({ parentfield: table, key: rowKey(identify(row))! }, change);
  }

  return computed<string[]>({
    get: () => rows.value.map((r) => r[linkFieldname()]).filter(Boolean),
    set: (selected) => {
      const fn = linkFieldname();
      // No link fieldname means child meta is missing; writing rows keyed by
      // "" would corrupt the child table, so skip the write entirely.
      if (!fn) return;
      const byValue = new Map(rows.value.map((r) => [r[fn], r]));
      const kept = new Set(selected);
      const next = selected.map((v) => byValue.get(v) ?? identify({ [fn]: v }));
      // Captured before the emit, which repoints `rows` at the new array.
      const removed = rows.value.filter((row) => !kept.has(row[fn]));
      const added = next.filter((row) => !byValue.has(row[fn]));
      emit("update:modelValue", next);
      emit("change", next);
      for (const row of removed) signal(row, "remove");
      for (const row of added) signal(row, "add");
    },
  });
}
