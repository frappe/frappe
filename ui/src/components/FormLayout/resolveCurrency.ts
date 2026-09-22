/**
 * Currency-code resolution for `FormLayout`'s `Currency` fields, mirroring Frappe
 * desk's `frappe.meta.get_field_currency`. The cross-record read goes through an
 * overridable `getDocValue` seam (built-in reader below, over the v2 list route).
 */
import { ref, shallowRef, type Ref } from "vue";
import { listDocuments } from "../../api";
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

/** One field of one record, keyed by doctype, name and field; the oldest goes past the cap. */
const values = new Map<string, Ref<string | null | undefined>>();
const MAX_VALUES = 500;

/** Built-in reader over the v2 list route; `undefined` until the read lands, never with no `window`. */
function builtinGetDocValue(
  doctype: string,
  name: string,
  field: string
): string | null | undefined {
  if (typeof window === "undefined") return undefined;

  const key = [doctype, name, field].join("\u0000");
  let value = values.get(key);
  // One ref per key: the calling computed re-runs when it lands, and a fresh read each
  // re-run would be a fetch storm.
  if (!value) {
    value = ref<string | null | undefined>(undefined);
    values.set(key, value);
    if (values.size > MAX_VALUES)
      values.delete(values.keys().next().value as string);
    // A failed read answers `null` and stays: forgetting it would retry on every re-run.
    readDocValue(doctype, name, field).then(
      (result) => (value.value = result),
      () => (value.value = null)
    );
  }
  return value.value;
}

/** `GET /document/<doctype>?fields=[field]&filters={name}`: one field, permission-checked. */
function readDocValue(
  doctype: string,
  name: string,
  field: string
): Promise<string | null> {
  return listDocuments(doctype, {
    fields: [field],
    filters: { name },
    limit: 1,
  }).then(({ data }) => {
    const value = data[0]?.[field];
    return value == null ? null : String(value);
  });
}

/** App/test override for the cross-record reader; mirrors `setFormatDefaults`. */
const override = shallowRef<DocValueReader | null>(null);

/** Point the resolver at a different record source; `null` restores the built-in. */
export function setDocValueReader(reader: DocValueReader | null): void {
  override.value = reader;
}

/** Restore the built-in reader and forget its reads (test isolation). */
export function resetDocValueReader(): void {
  override.value = null;
  values.clear();
}

/** The active cross-record reader: the override if set, else the built-in. */
export function getDocValueReader(): DocValueReader {
  return override.value ?? builtinGetDocValue;
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
