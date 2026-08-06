import { computed } from "vue";
import type { Ref } from "vue";
import { buildLayoutFromMeta } from "./buildLayoutFromMeta";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import type { FormLayoutSchema, RawMetaField } from "./types";

export interface UseDoctypeLayout {
  /** Render-ready schema; empty until meta loads (or if the doctype is absent). */
  layout: Ref<FormLayoutSchema>;
  loading: Ref<boolean>;
  error: Ref<unknown>;
  /** Re-fetch the meta and rebuild the layout. */
  reload: () => void;
}

/** Memoised per doctype so every caller shares one layout instance. */
const cache = new Map<string, UseDoctypeLayout>();

/**
 * Produce a `FormLayoutSchema` from a doctype's meta (via `useDoctypeMeta`).
 * Layout-only — pairing it with a doc is the consumer's job. Child-table columns
 * come from the sibling child metas the same `getdoctype` call returned.
 */
export function useDoctypeLayout(doctype: string): UseDoctypeLayout {
  const cached = cache.get(doctype);
  if (cached) return cached;

  const { meta, metas, loading, error, reload } = useDoctypeMeta(doctype);

  const layout = computed<FormLayoutSchema>(() => {
    if (!meta.value) return [];
    const childMetas: Record<string, RawMetaField[]> = {};
    for (const [name, m] of Object.entries(metas.value)) {
      if (m.fields) childMetas[name] = m.fields;
    }
    return buildLayoutFromMeta(meta.value.fields ?? [], { childMetas });
  });

  const result: UseDoctypeLayout = { layout, loading, error, reload };
  cache.set(doctype, result);
  return result;
}
