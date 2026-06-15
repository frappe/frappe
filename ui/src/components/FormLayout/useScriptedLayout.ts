import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useDoctypeLayout } from './useDoctypeLayout'
import type { UseDoctypeLayout } from './useDoctypeLayout'
import { applyMetaScript } from './applyMetaScript'
import type { MetaOp } from './applyMetaScript'
import type { FormLayoutSchema } from './types'

/**
 * Compose `useDoctypeLayout` (meta → schema) with `applyMetaScript` (the
 * meta/layout scripting seam), so a caller gets a **scripted** layout straight
 * from a doctype name:
 *
 *   useDoctypeLayout(dt) → [ applyMetaScript(ops) ] → FormLayout
 *
 * App-agnostic: it references no app-specific doctype and fetches no script — the
 * caller supplies the `ops`. This is the host-side convenience that wires the
 * transform into the real meta path (vs the in-memory hand-written schema demo).
 * `ops` may be a plain array, a ref, or a getter; when it's reactive, changing it
 * re-runs the transform and the form re-renders. The underlying meta fetch is
 * still shared/memoised by `useDoctypeLayout`.
 *
 * In the real product, `ops` is where a server-stored script's resolved
 * `setFieldProperty`/`addField` patches plug in (Phase 7 / syntax layer). Here it
 * stays a value the caller owns — the lib gains no script storage.
 */
export function useScriptedLayout(
  doctype: string,
  ops: MaybeRefOrGetter<MetaOp[]>,
): UseDoctypeLayout {
  const base = useDoctypeLayout(doctype)

  const layout = computed<FormLayoutSchema>(() =>
    applyMetaScript(base.layout.value, toValue(ops) ?? []),
  )

  return { layout, loading: base.loading, error: base.error, reload: base.reload }
}
