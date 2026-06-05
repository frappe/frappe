import { computed, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { createResource, frappeRequest } from 'frappe-ui'
import type { RawMetaField } from './types'

export interface DoctypeMeta {
  name: string
  fields?: RawMetaField[]
}

interface GetDoctypeResponse {
  docs?: DoctypeMeta[]
  user_settings?: string
}

export interface UseDoctypeMeta {
  /** The requested doctype's meta; `null` until it loads (or if absent). */
  meta: Ref<DoctypeMeta | null>
  /**
   * Every doctype meta returned by `getdoctype`, keyed by name. With
   * `with_parent: 1` this includes the parent **and** its child-table metas —
   * the source `buildLayoutFromMeta` reads to resolve `Table` columns.
   */
  metas: Ref<Record<string, DoctypeMeta>>
  loading: Ref<boolean>
  error: Ref<unknown>
  /** Re-fetch the meta. */
  reload: () => void
}

/**
 * Memoised per doctype: the `getdoctype` resource is created and fetched once per
 * session, then shared by every caller (and by `useDoctypeLayout`).
 */
const cache = new Map<string, UseDoctypeMeta>()

/**
 * Fetch a doctype's meta via standard Frappe
 * (`frappe.desk.form.load.getdoctype`, `with_parent: 1`) and expose it as a
 * name-keyed map plus the requested doctype's own meta.
 *
 * Fetch-only: it returns raw meta + load state, never a layout schema — building
 * the `FormLayoutSchema` is `useDoctypeLayout`'s job. Keeping the two seams
 * separate lets a Table grid reuse the same child-table metas this already
 * fetched, without a second round-trip.
 */
export function useDoctypeMeta(doctype: string): UseDoctypeMeta {
  const cached = cache.get(doctype)
  if (cached) return cached

  const metas = ref<Record<string, DoctypeMeta>>({})
  const error = ref<unknown>(null)

  const resource = createResource({
    url: 'frappe.desk.form.load.getdoctype',
    params: { doctype, with_parent: 1, cached_timestamp: null },
    cache: ['Meta', doctype],
    resourceFetcher: frappeRequest,
    onError: (err: unknown) => {
      metas.value = {}
      error.value = err
    },
  })

  // Driven off `resource.data` (not `onSuccess`) so it also works when
  // `createResource` hands back a resource already cached/shared on the same
  // `['Meta', …]` key — its data is present immediately and `onSuccess` would
  // not re-fire.
  watch(
    () => resource.data as GetDoctypeResponse | null,
    (res) => {
      if (!res) return
      const map: Record<string, DoctypeMeta> = {}
      for (const d of res.docs ?? []) map[d.name] = d
      metas.value = map
      error.value = map[doctype]
        ? null
        : new Error(`Doctype meta not found for "${doctype}".`)
    },
    { immediate: true },
  )

  // Only hit the network if nothing has fetched this meta yet.
  if (!resource.fetched && !resource.loading) resource.fetch()

  const result: UseDoctypeMeta = {
    meta: computed(() => metas.value[doctype] ?? null),
    metas,
    loading: computed(() => resource.loading),
    error,
    reload: () => resource.reload(),
  }
  cache.set(doctype, result)
  return result
}
