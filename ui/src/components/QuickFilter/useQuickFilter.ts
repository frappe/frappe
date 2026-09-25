import { computed, ref } from "vue";
import type { Ref, WritableComputedRef } from "vue";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { getFilterableFields } from "../Filter/getFilterableFields";
import type { FilterField } from "../Filter/types";
import { getQuickFilterFields } from "./getQuickFilterFields";

export interface UseQuickFilter {
  /** The fields surfaced as QuickFilter inputs. Defaults to the doctype's
   *  `in_standard_filter` fields (from Meta) until customized; a host may bind this
   *  (alongside QuickFilter's `v-model:fields`) to persist the choice. */
  fields: WritableComputedRef<FilterField[]>;
  /** Whether the quick-filter strip is in customize (edit) mode. Owned here so a
   *  customize trigger can live anywhere — not just beside QuickFilter — and still
   *  drive its edit state. QuickFilter `v-model:customizing`s this. */
  customizing: Ref<boolean>;
  /** Whether the doctype offers any filterable field to surface — a trigger reads
   *  this to hide itself when there is nothing to customize. */
  canCustomize: Ref<boolean>;
}

/**
 * Owns the QuickFilter strip's surfaced fields and its customize edit-mode. Reads
 * Meta itself (cached per doctype) so it's self-contained.
 *
 * `doctype` is taken by value: the Shell remounts the controls via `:key="doctype"`
 * and Meta is cached per doctype string, so reconstructing on a switch is cheap.
 */
export function useQuickFilter(doctype: string): UseQuickFilter {
  const { meta } = useDoctypeMeta(doctype);

  // `null` ⇒ "use the Meta-derived default"; a value ⇒ the host/user customized it.
  // A writable computed so the default tracks Meta as it loads, yet a customization
  // (via `v-model:fields`) sticks — no seed watch needed.
  const customFields = ref<FilterField[] | null>(null);
  const fields = computed<FilterField[]>({
    get: () =>
      customFields.value ??
      getQuickFilterFields(meta.value?.fields ?? [], doctype),
    set: (value) => {
      customFields.value = value;
    },
  });

  const customizing = ref(false);
  const canCustomize = computed(
    () => getFilterableFields(meta.value?.fields ?? [], doctype).length > 0
  );

  return { fields, customizing, canCustomize };
}
