/**
 * Currency-code resolution for `FormLayout`'s `Currency` fields, mirroring Frappe
 * desk's `frappe.meta.get_field_currency`. The cross-record read goes through an
 * overridable `getDocValue` seam (built-in reader below).
 */
import { shallowRef } from "vue";
import { createResource, getCachedResource } from "frappe-ui";
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

/** Cache namespace for the resources frappe-ui keys by doctype/name/field. */
const CACHE_NS = "FormLayout:field_currency";

/**
 * Built-in reader, backed by frappe-ui's resource cache. Returns `undefined`
 * until the fetch lands (and always when there's no `window`); the reactive
 * `.data` re-runs the calling computed.
 *
 * The `getCachedResource` lookup matters: re-`createResource`-ing with the same
 * `cache` key while `auto` is set would `reload()` on every computed re-run (a
 * fetch storm), so the resource is created once and reused.
 */
function builtinGetDocValue(
  doctype: string,
  name: string,
  field: string
): string | null | undefined {
  if (typeof window === "undefined") return undefined;

  const cacheKey = [CACHE_NS, doctype, name, field];
  const resource =
    getCachedResource(cacheKey) ??
    createResource({
      url: "frappe.client.get_value",
      params: { doctype, filters: name, fieldname: field },
      cache: cacheKey,
      auto: true,
    });
  // `frappe.client.get_value` returns `{ [field]: value }`; `.data` is reactive.
  return resource.data?.[field] ?? undefined;
}

/** App/test override for the cross-record reader; mirrors `setFormatDefaults`. */
const override = shallowRef<DocValueReader | null>(null);

/** Point the resolver at a different record source; `null` restores the built-in. */
export function setDocValueReader(reader: DocValueReader | null): void {
  override.value = reader;
}

/** Restore the built-in `frappe.client.get_value` reader (test isolation). */
export function resetDocValueReader(): void {
  override.value = null;
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
