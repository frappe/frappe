import { computed, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { createResource, frappeRequest } from 'frappe-ui'
import { buildLayoutFromMeta } from './buildLayoutFromMeta'
import type { FormLayoutSchema, RawMetaField } from './types'

interface DoctypeMeta {
  name: string
  fields?: RawMetaField[]
}

interface GetDoctypeResponse {
  docs?: DoctypeMeta[]
  user_settings?: string
}

export interface UseDoctypeLayout {
  /** Render-ready schema; empty until meta loads (or if the doctype is absent). */
  layout: Ref<FormLayoutSchema>
  loading: Ref<boolean>
  error: Ref<unknown>
  /** Re-fetch the meta and rebuild the layout. */
  reload: () => void
}

/**
 * Memoised per doctype: a given doctype's meta is fetched and its layout built
 * once per session, then shared by every caller. `reload()` refreshes in place.
 */
const cache = new Map<string, UseDoctypeLayout>()

/**
 * Fetch a doctype's meta via standard Frappe (`frappe.desk.form.load.getdoctype`)
 * and produce a `FormLayoutSchema` for `FormLayout`.
 *
 * Layout-only: returns the schema + load state. It does **not** fetch or manage
 * the doc — pairing the layout with a doc (`useDoc`, a fresh `reactive({})`, …)
 * is the consumer's job.
 */
export function useDoctypeLayout(doctype: string): UseDoctypeLayout {
  const cached = cache.get(doctype)
  if (cached) return cached

  const layout = ref<FormLayoutSchema>([])
  const error = ref<unknown>(null)

  const resource = createResource({
    url: 'frappe.desk.form.load.getdoctype',
    params: { doctype, with_parent: 1, cached_timestamp: null },
    cache: ['Meta', doctype],
    resourceFetcher: frappeRequest,
    onError: (err: unknown) => {
      layout.value = []
      error.value = err
    },
  })

  // Rebuild whenever meta data lands. Driven off `resource.data` (not
  // `onSuccess`) so it also works when `createResource` hands back a resource
  // already cached/shared by another part of the app on the same `['Meta', …]`
  // key — its data is present immediately and `onSuccess` would not re-fire.
  watch(
    () => resource.data as GetDoctypeResponse | null,
    (res) => {
      if (!res) return
      const meta = res.docs?.find((d) => d.name === doctype)
      if (!meta) {
        layout.value = []
        error.value = new Error(`Doctype meta not found for "${doctype}".`)
        return
      }
      error.value = null
      layout.value = buildLayoutFromMeta(meta.fields ?? [])
    },
    { immediate: true },
  )

  // Only hit the network if nothing has fetched this meta yet.
  if (!resource.fetched && !resource.loading) resource.fetch()

  const result: UseDoctypeLayout = {
    layout,
    loading: computed(() => resource.loading),
    error,
    reload: () => resource.reload(),
  }
  cache.set(doctype, result)
  return result
}
