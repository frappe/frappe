// What `page.cached` fetched for a record, kept while the record's complete entry stays in the shared cache.
import { documentKey, onRecordLeft, readCachedDocument } from "@framework/ui/cache";

const kept = new Map<string, Map<string, unknown>>();

onRecordLeft((doctype, name) => kept.delete(documentKey(doctype, name)));

/** The value an earlier visit fetched for the key, or undefined when none is kept. */
export function keptValue(doctype: string, name: string, key: string): { value: unknown } | undefined {
  const values = kept.get(documentKey(doctype, name));
  return values?.has(key) ? { value: values.get(key) } : undefined;
}

/** Taken when a fetch starts: it drops the write once the record's complete entry has left since, or when there was none. */
export function keeperFor(doctype: string, name: string): (key: string, value: unknown) => void {
  if (!readCachedDocument(doctype, name)?.complete) return () => {};
  const record = documentKey(doctype, name);
  const values = kept.get(record) ?? new Map<string, unknown>();
  kept.set(record, values);
  return (key, value) => {
    if (kept.get(record) === values) values.set(key, value);
  };
}

export function resetKeptValues() {
  kept.clear();
}
