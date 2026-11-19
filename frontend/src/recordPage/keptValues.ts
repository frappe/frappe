// What `page.cached` fetched for a record, kept while the record's complete entry stays in the shared cache.
import { documentKey, onRecordLeft, readCachedDocument } from "@framework/ui/cache";

const KEY_LIMIT = 20;

// Record, then script, then key; least recently used key first.
type Values = Map<string, unknown>;
const kept = new Map<string, Map<string, Values>>();

onRecordLeft((doctype, name) => kept.delete(documentKey(doctype, name)));

/** The value an earlier visit fetched for the script's key, or undefined when none is kept. */
export function keptValue(
  doctype: string,
  name: string,
  source: string,
  key: string,
): { value: unknown } | undefined {
  const values = kept.get(documentKey(doctype, name))?.get(source);
  if (!values?.has(key)) return undefined;
  const value = values.get(key);
  use(values, key, value);
  return { value };
}

/** Taken when a fetch starts: it drops the write once the record's complete entry has left since, or when there was none. */
export function keeperFor(
  doctype: string,
  name: string,
): (source: string, key: string, value: unknown) => void {
  if (!readCachedDocument(doctype, name)?.complete) return () => {};
  const record = documentKey(doctype, name);
  const scripts = kept.get(record) ?? new Map<string, Values>();
  kept.set(record, scripts);
  return (source, key, value) => {
    if (kept.get(record) !== scripts) return;
    const values = scripts.get(source) ?? new Map<string, unknown>();
    scripts.set(source, values);
    use(values, key, value);
    for (const oldest of values.keys()) {
      if (values.size <= KEY_LIMIT) return;
      values.delete(oldest);
    }
  };
}

export function resetKeptValues() {
  kept.clear();
}

function use(values: Values, key: string, value: unknown) {
  values.delete(key);
  values.set(key, value);
}
