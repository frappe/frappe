// The list entry's key, and which list reads the cache takes.
import type { ListQuery } from "../api";

const KEY_PARTS = ["filters", "or_filters", "order_by", "group_by", "fields"] as const;
const PLAIN_FIELD = /^[A-Za-z0-9_]+$/;

export function listCacheKey(doctype: string, query: ListQuery): string {
  const parts: Record<string, unknown> = {};
  for (const part of KEY_PARTS) {
    if (query[part] !== undefined) parts[part] = query[part];
  }
  if (query.fields) parts.fields = keyFields(query.fields);
  return `${doctype}\u0000${JSON.stringify(sortKeys(parts))}`;
}

/** A grouped read or a computed field gives rows that are not documents. */
export function isFeedableQuery(query: ListQuery): boolean {
  if (query.group_by) return false;
  return (query.fields ?? []).every((field) => field === "*" || PLAIN_FIELD.test(field));
}

/** The wrapper adds `modified` to every list read, so a query with or without it is one list. */
function keyFields(fields: readonly string[]): string[] {
  const unique = new Set(fields);
  if (!unique.has("*")) unique.add("modified");
  return [...unique].sort();
}

function sortKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value === null || typeof value !== "object") return value;
  const sorted: Record<string, unknown> = {};
  for (const key of Object.keys(value).sort()) {
    const item = (value as Record<string, unknown>)[key];
    if (item !== undefined) sorted[key] = sortKeys(item);
  }
  return sorted;
}
