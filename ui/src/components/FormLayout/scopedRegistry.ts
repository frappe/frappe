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
import { getCurrentScope, onScopeDispose } from "vue";

/** One scoped override; a fresh object so same-value frames stay distinguishable. */
interface Frame<V> {
  value: V;
}

/** Per-key: the entry that pre-existed the first override, plus a stack of overrides. */
interface Record<V> {
  base: { had: boolean; value: V | undefined };
  stack: Frame<V>[];
}

// Per-map bookkeeping. A plain snapshot-and-restore can't tell two *same-value*
// overrides apart (e.g. an HMR reload, or the same overriding component mounted
// twice, both registering the same field component): the first scope to dispose
// would see its value still in the map and wrongly restore the base while the
// second instance is still relying on the override. A stack keyed per entry frame
// makes overlapping overrides — same value or not — restore in the right order.
const registries = new WeakMap<
  Map<unknown, unknown>,
  Map<unknown, Record<unknown>>
>();

/**
 * Set `key` → `value` in `map`, scoped to the current Vue effect scope. The newest
 * override wins while active; on scope dispose the map falls back to the next-most-
 * recent still-active override, or to the entry that pre-existed all overrides
 * (restored or deleted). A foreign direct write to `map` supersedes the stack and
 * is never clobbered.
 *
 * Returns `true` if the scoped write happened, or `false` when there is **no**
 * active scope to tie cleanup to (nothing is written — the caller decides the
 * fallback, e.g. a global write + warning).
 */
export function setScoped<K, V>(map: Map<K, V>, key: K, value: V): boolean {
  if (!getCurrentScope()) return false;

  let perKey = registries.get(map) as Map<K, Record<V>> | undefined;
  if (!perKey)
    registries.set(
      map,
      (perKey = new Map<K, Record<V>>()) as Map<unknown, Record<unknown>>
    );

  let record = perKey.get(key);
  if (!record) {
    // First override for this key: snapshot the pre-existing (base) entry once.
    record = { base: { had: map.has(key), value: map.get(key) }, stack: [] };
    perKey.set(key, record);
  }

  const frame: Frame<V> = { value };
  record.stack.push(frame);
  map.set(key, value);

  onScopeDispose(() => {
    const { stack } = record!;
    const index = stack.indexOf(frame);
    if (index === -1) return;
    const wasTop = index === stack.length - 1;
    stack.splice(index, 1);

    // Only touch the map if THIS frame was the effective override and no foreign
    // write has since replaced it; otherwise a newer scope (or a direct write)
    // owns the entry and we leave it alone.
    if (wasTop && map.get(key) === frame.value) {
      const top = stack[stack.length - 1];
      if (top) map.set(key, top.value);
      else if (record!.base.had) map.set(key, record!.base.value as V);
      else map.delete(key);
    }

    if (stack.length === 0) perKey!.delete(key);
  });

  return true;
}
