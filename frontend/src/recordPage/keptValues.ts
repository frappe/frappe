// What `page.cached` fetched for a record, kept while the record's complete entry stays in the shared cache.
import { onRecordLeft, readCachedDocument } from "@framework/ui/cache";

const kept = new Map<string, Map<string, unknown>>();

onRecordLeft((doctype, name) => kept.delete(recordKey(doctype, name)));

/** The value an earlier visit fetched for the key, or undefined when none is kept. */
export function keptValue(doctype: string, name: string, key: string): { value: unknown } | undefined {
  const values = kept.get(recordKey(doctype, name));
  return values?.has(key) ? { value: values.get(key) } : undefined;
}

/** Keeps nothing for a record the shared cache holds no complete entry of, so nothing outlives its entry. */
export function keepValue(doctype: string, name: string, key: string, value: unknown) {
  if (!readCachedDocument(doctype, name)?.complete) return;
  const record = recordKey(doctype, name);
  const values = kept.get(record) ?? new Map<string, unknown>();
  values.set(key, value);
  kept.set(record, values);
}

export function resetKeptValues() {
  kept.clear();
}

function recordKey(doctype: string, name: string) {
  return `${doctype}\u0000${name}`;
}
