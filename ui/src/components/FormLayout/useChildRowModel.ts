import { computed } from "vue";
import type { WritableComputedRef } from "vue";

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
  emit: ChildRowEmit
): WritableComputedRef<string[]> {
  const rows = computed<Record<string, any>[]>(() => {
    const v = modelValue();
    return Array.isArray(v) ? v : [];
  });

  return computed<string[]>({
    get: () => rows.value.map((r) => r[linkFieldname()]).filter(Boolean),
    set: (selected) => {
      const fn = linkFieldname();
      // No link fieldname means child meta is missing; writing rows keyed by
      // "" would corrupt the child table, so skip the write entirely.
      if (!fn) return;
      const byValue = new Map(rows.value.map((r) => [r[fn], r]));
      const next = selected.map((v) => byValue.get(v) ?? { [fn]: v });
      emit("update:modelValue", next);
      emit("change", next);
    },
  });
}
