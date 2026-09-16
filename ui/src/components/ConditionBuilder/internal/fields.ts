import { computed, watch } from "vue";
import type { ComputedRef } from "vue";
import { useDoctypeMeta } from "../../../composables/useDoctypeMeta";
import { getFilterableFields } from "../../Filter/getFilterableFields";
import { toConditionExpression } from "../adapters";
import type {
  ConditionField,
  ConditionGroup,
  FieldConditionValue,
} from "../types";

/**
 * The doctype's fields, and the expression the tree compiles to with them.
 *
 * `doctype` is read once, at setup: `useDoctypeMeta` starts a request, so a host
 * switching doctype remounts with `:key` rather than fetching each one.
 */
export function useConditionFields<T>(
  props: { doctype?: string; fields?: ConditionField[]; fieldPrefix?: string },
  tree: ComputedRef<ConditionGroup<T>>,
  emitExpression: (value: string) => void
) {
  const doctype = props.fields ? "" : props.doctype ?? "";
  const meta = doctype ? useDoctypeMeta(doctype) : null;

  const fields = computed<ConditionField[]>(() => {
    if (props.fields) return props.fields;
    const loaded = meta?.meta.value;
    if (!loaded) return [];
    return getFilterableFields(loaded.fields ?? [], doctype);
  });

  const fieldsLoading = computed(() =>
    Boolean(meta && meta.loading.value && !meta.meta.value)
  );

  // A failed request looks like every field being deleted. The alert says
  // otherwise.
  const fieldsError = computed<unknown>(() => (meta ? meta.error.value : null));

  function reloadFields() {
    meta?.reload();
  }

  /**
   * Re-emitted when the fields arrive, since Check and numeric fields compile
   * from their fieldtype rather than their value.
   */
  const expression = computed(() =>
    toConditionExpression(
      tree.value as unknown as ConditionGroup<FieldConditionValue>,
      {
        // An empty list is Meta in flight or failed, not a doctype with no
        // fields. Withheld so the compiler's value-reading fallback runs.
        fields: fields.value.length ? fields.value : undefined,
        fieldPrefix: props.fieldPrefix,
      }
    )
  );

  // Withheld while fields are loading or failed: the guessing fallback would
  // overwrite a correct stored expression. In the watch source, not a bare
  // guard, so it still fires when that flips.
  watch(
    [expression, fieldsLoading, fieldsError],
    ([value, loading, error]) => {
      if (loading || error) return;
      emitExpression(value);
    },
    { immediate: true }
  );

  return { fields, fieldsLoading, fieldsError, reloadFields };
}
