/**
 * Currency-code resolution for `FormLayout`'s `Currency` fields, mirroring Frappe
 * desk's `frappe.meta.get_field_currency`. The cross-record read goes through an
 * overridable `getDocValue` seam (built-in reader below, over the shared data cache).
 */
import { getCurrentScope, onScopeDispose, shallowRef } from "vue";
import { getDocumentFields } from "../../api";
import { holdDocument, readCachedDocument } from "../../cache";
import { pickSiblingValue } from "./pickSiblingValue";
import type { RecordContext } from "./pickSiblingValue";

/** Reads a single field off another record. May return `undefined` while the
 *  fetch is in flight — callers fall back. */
export type DocValueReader = (
  doctype: string,
  name: string,
  field: string
) => string | null | undefined;

/** Context for resolving a Currency field's currency code. */
export interface CurrencyResolveContext extends RecordContext {
  /** Site default currency (`getFormatDefaults().currency`); the final fallback. */
  defaultCurrency?: string | null;
  /** Cross-record reader; defaults to {@link getDocValueReader}. */
  getDocValue?: DocValueReader;
}

// --- Built-in runtime reader -------------------------------------------------

/** Each doctype, name and field that readers on screen use: how many, and the cache hold. */
const readers = new Map<string, { count: number; release: () => void }>();

/** The reader for one component; the first reader on screen reads the value into the cache. */
export function useDocValueReader(): DocValueReader {
  // With no scope nothing would release the value, so the reader reads the cache alone.
  if (!getCurrentScope()) return (...args) => getDocValueReader()(...args);
  const used = new Set<string>();
  onScopeDispose(() => used.forEach(release));
  return (doctype, name, field) => {
    if (override.value) return override.value(doctype, name, field);
    const key = [doctype, name, field].join("\u0000");
    if (!used.has(key)) {
      used.add(key);
      use(key, doctype, name, field);
    }
    return readCachedValue(doctype, name, field);
  };
}

/** The linked record's value in the shared data cache; `undefined` when its entry lacks it. */
function readCachedValue(
  doctype: string,
  name: string,
  field: string
): string | null | undefined {
  const doc = readCachedDocument(doctype, name)?.doc;
  if (!doc || !(field in doc)) return undefined;
  const value = doc[field];
  return value == null ? null : String(value);
}

function use(key: string, doctype: string, name: string, field: string): void {
  const reader = readers.get(key);
  if (reader) {
    reader.count++;
    return;
  }
  readers.set(key, { count: 1, release: holdDocument(doctype, name) });
  // A failed read leaves the entry as it was; the next visit reads again.
  if (typeof window !== "undefined") getDocumentFields(doctype, name, [field]).catch(() => {});
}

function release(key: string): void {
  const reader = readers.get(key);
  if (!reader || --reader.count > 0) return;
  readers.delete(key);
  reader.release();
}

/** App/test override for the cross-record reader; mirrors `setFormatDefaults`. */
const override = shallowRef<DocValueReader | null>(null);

/** Point the resolver at a different record source; `null` restores the built-in. */
export function setDocValueReader(reader: DocValueReader | null): void {
  override.value = reader;
}

/** Restore the built-in reader and forget which values are in use (test isolation). */
export function resetDocValueReader(): void {
  override.value = null;
  readers.forEach((reader) => reader.release());
  readers.clear();
}

/** The active cross-record reader: the override if set, else a read of the cache alone. */
export function getDocValueReader(): DocValueReader {
  return override.value ?? readCachedValue;
}

// --- Resolution --------------------------------------------------------------

/**
 * Resolve a Currency field's currency code from its `options`, mirroring Frappe
 * desk's `frappe.meta.get_field_currency`:
 *  1. No `options` → site default currency.
 *  2. A sibling fieldname → that field's value (row col, then doc, then parent).
 *  3. `Doctype:link_field:currency_field` → currency read off the linked record.
 * Anything unresolved falls back to the default.
 */
export function resolveFieldCurrency(
  options: string | undefined | null,
  ctx: CurrencyResolveContext = {}
): string | undefined {
  const fallback = ctx.defaultCurrency || undefined;
  if (!options) return fallback;

  if (options.indexOf(":") !== -1) {
    const [doctype, linkField, currencyField] = options.split(":");
    if (doctype && linkField && currencyField) {
      const name = pickSiblingValue(ctx, linkField);
      if (name) {
        const getDocValue = ctx.getDocValue ?? getDocValueReader();
        const currency = getDocValue(doctype, String(name), currencyField);
        if (currency) return currency;
      }
    }
    return fallback;
  }

  const sibling = pickSiblingValue(ctx, options);
  if (typeof sibling === "string" && sibling) return sibling;
  return fallback;
}
