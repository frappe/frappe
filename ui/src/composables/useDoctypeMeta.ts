import { computed, ref, watch } from "vue";
import type { Ref } from "vue";
import { createResource, frappeRequest } from "frappe-ui";
import type { RawMetaField } from "../components/FormLayout/types";

export interface DoctypeMeta {
  name: string;
  title_field?: string;
  fields?: RawMetaField[];
}

interface GetDoctypeResponse {
  docs?: DoctypeMeta[];
  user_settings?: string;
}

export interface UseDoctypeMeta {
  /** The requested doctype's meta; `null` until it loads (or if absent). */
  meta: Ref<DoctypeMeta | null>;
  /** Every doctype meta from `getdoctype`, keyed by name. `with_parent: 1`
   *  includes child-table metas, used to resolve `Table` columns. */
  metas: Ref<Record<string, DoctypeMeta>>;
  loading: Ref<boolean>;
  error: Ref<unknown>;
  /** Re-fetch the meta. */
  reload: () => void;
}

/** Memoised per doctype: fetched once per session, shared by every caller. */
const cache = new Map<string, UseDoctypeMeta>();

/**
 * Fetch a doctype's meta via `frappe.desk.form.load.getdoctype` (`with_parent: 1`)
 * and expose it as a name-keyed map plus the requested doctype's own meta.
 * Fetch-only — building the layout schema is `useDoctypeLayout`'s job.
 */
export function useDoctypeMeta(doctype: string): UseDoctypeMeta {
  const cached = cache.get(doctype);
  if (cached) return cached;

  const metas = ref<Record<string, DoctypeMeta>>({});
  const error = ref<unknown>(null);

  const resource = createResource({
    url: "frappe.desk.form.load.getdoctype",
    params: { doctype, with_parent: 1, cached_timestamp: null },
    cache: ["Meta", doctype],
    resourceFetcher: frappeRequest,
    onError: (err: unknown) => {
      metas.value = {};
      error.value = err;
    },
  });

  // Driven off `resource.data` (not `onSuccess`) so it also fires for an
  // already-cached resource on the same `['Meta', …]` key, where `onSuccess` wouldn't.
  watch(
    () => resource.data as GetDoctypeResponse | null,
    (res) => {
      if (!res) return;
      const map: Record<string, DoctypeMeta> = {};
      for (const d of res.docs ?? []) map[d.name] = d;
      metas.value = map;
      error.value = map[doctype]
        ? null
        : new Error(`Doctype meta not found for "${doctype}".`);
    },
    { immediate: true }
  );

  // Only hit the network if nothing has fetched this meta yet.
  if (!resource.fetched && !resource.loading) resource.fetch();

  const result: UseDoctypeMeta = {
    meta: computed(() => metas.value[doctype] ?? null),
    metas,
    loading: computed(() => resource.loading),
    error,
    reload: () => resource.reload(),
  };
  cache.set(doctype, result);
  return result;
}
