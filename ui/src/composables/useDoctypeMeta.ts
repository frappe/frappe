import { computed, ref, toValue, watch } from "vue";
import type { ComputedRef, MaybeRefOrGetter, Ref } from "vue";
import { createResource, frappeRequest } from "frappe-ui";
import type { RawMetaField } from "../components/FormLayout/types";
import { memoizedState } from "../utils/sharedState";

/** A DocPerm row as `getdoctype` returns it; booleans arrive as `0 | 1`. */
export interface DocPermRow {
  role: string;
  permlevel?: number;
  read?: 0 | 1;
  write?: 0 | 1;
  [right: string]: unknown;
}

export interface DoctypeMeta {
  name: string;
  title_field?: string;
  fields?: RawMetaField[];
  permissions?: DocPermRow[];
}

interface GetDoctypeResponse {
  docs?: DoctypeMeta[];
  user_settings?: string;
}

export interface UseDoctypeMeta {
  /** The requested doctype's meta; `null` until it loads (or if absent). */
  meta: ComputedRef<DoctypeMeta | null>;
  /** Every doctype meta from `getdoctype`, keyed by name. `with_parent: 1`
   *  includes child-table metas, used to resolve `Table` columns. */
  metas: ComputedRef<Record<string, DoctypeMeta>>;
  loading: ComputedRef<boolean>;
  error: ComputedRef<unknown>;
  /** Re-fetch the meta. */
  reload: () => void;
}

interface DoctypeMetaEntry {
  metas: Ref<Record<string, DoctypeMeta>>;
  error: Ref<unknown>;
  loading: ComputedRef<boolean>;
  reload: () => void;
}

/** Memoised per doctype: fetched once per session, shared by every caller. */
const entries = memoizedState((doctype: string) => doctype, buildEntry);

/**
 * Fetch a doctype's meta via `frappe.desk.form.load.getdoctype` (`with_parent: 1`)
 * and expose it as a name-keyed map plus the requested doctype's own meta.
 * Fetch-only — building the layout schema is `buildLayoutFromMeta`'s job
 * (or `joinLayout`'s, on the stored Form Layout path).
 */
export function useDoctypeMeta(
  doctype: MaybeRefOrGetter<string>
): UseDoctypeMeta {
  // Warm the current entry at call time; the computed tracks it from there.
  const current = () => entries.get(toValue(doctype));
  current();
  const entry = computed(current);

  return {
    meta: computed(() => entry.value.metas.value[toValue(doctype)] ?? null),
    metas: computed(() => entry.value.metas.value),
    loading: computed(() => entry.value.loading.value),
    error: computed(() => entry.value.error.value),
    reload: () => entry.value.reload(),
  };
}

/** Drops every memoised meta, so one test's fetch cannot reach the next. */
export function resetDoctypeMeta(): void {
  entries.reset();
}

function buildEntry(doctype: string): DoctypeMetaEntry {
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

  return {
    metas,
    error,
    loading: computed(() => resource.loading),
    reload: () => resource.reload(),
  };
}
