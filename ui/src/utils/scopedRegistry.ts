/**
 * Scoped mutation of a plain `Map` registry, tied to the current Vue effect
 * scope. Backs the fieldtype registry's `{ global: false }` registrations:
 * override an entry, then restore it on scope dispose so it doesn't leak
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

// A per-key stack (not a plain snapshot) so two *same-value* overlapping
// overrides (HMR reload, same component mounted twice) restore in the right
// order — a snapshot would let the first disposer wrongly restore the base.
const registries = new WeakMap<
  Map<unknown, unknown>,
  Map<unknown, Record<unknown>>
>();

/**
 * Set `key` → `value` in `map`, scoped to the current Vue effect scope; restored
 * on dispose. A foreign direct write to `map` supersedes the stack and is never
 * clobbered. Returns `false` (writing nothing) when there's no active scope to
 * tie cleanup to — the caller decides the fallback.
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

    // Only restore if THIS frame is still the effective override; otherwise a
    // newer scope or a direct write owns the entry — leave it alone.
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
