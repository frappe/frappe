/**
 * Scoped mutation of a plain `Map` registry, tied to the current Vue effect
 * scope. Pure and app-agnostic: no `.vue`, no globals — just a Map + Vue's scope
 * lifecycle — so it unit-tests standalone (drive it with `effectScope()`).
 *
 * Used by the fieldtype registry to support `{ global: false }` registrations:
 * snapshot the prior entry, set the new one, and **restore** it when the calling
 * component's scope disposes (unmount) — so a per-component override doesn't leak
 * process-wide.
 */
import { getCurrentScope, onScopeDispose } from 'vue'

/**
 * Set `key` → `value` in `map`, scoped to the current Vue effect scope. The prior
 * entry (present or absent) is snapshotted and restored on scope dispose — unless
 * a later write replaced our value, in which case that newer write wins and we
 * leave it alone.
 *
 * Returns `true` if the scoped write happened, or `false` when there is **no**
 * active scope to tie cleanup to (nothing is written — the caller decides the
 * fallback, e.g. a global write + warning).
 */
export function setScoped<K, V>(map: Map<K, V>, key: K, value: V): boolean {
  if (!getCurrentScope()) return false

  const had = map.has(key)
  const previous = map.get(key)
  map.set(key, value)

  onScopeDispose(() => {
    if (map.get(key) !== value) return // a later write superseded us — don't clobber it
    if (had) map.set(key, previous as V)
    else map.delete(key)
  })

  return true
}
