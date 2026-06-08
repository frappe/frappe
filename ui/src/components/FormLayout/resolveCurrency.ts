/**
 * Currency-code resolution for `FormLayout`'s `Currency` fields, mirroring Frappe
 * desk's `frappe.meta.get_field_currency`.
 *
 * The pure *number/currency formatting* lives in `formatNumber.ts` (no Vue, no
 * globals). Resolving *which* currency a field uses, however, can need a read of
 * another record (the `Doctype:link_field:currency_field` options form) — a
 * Frappe-runtime concern. So this module owns the runtime seam, the same way
 * `formatDefaults.ts` owns the `window.sysdefaults` read: the field component
 * just calls `resolveFieldCurrency`, and the cross-record read happens here
 * behind a built-in (overridable) `getDocValue`.
 *
 * The built-in reader fetches `frappe.client.get_value` lazily through frappe-ui's
 * own resource cache: the first synchronous call misses (`.data` is `undefined`
 * so the field shows the default currency), the fetch fills the resource's
 * **reactive** `.data`, and any `computed` that resolved a currency re-runs and
 * picks up the real code. frappe-ui owns the dedupe + caching, so this module
 * keeps none of its own.
 */
import { shallowRef } from "vue";
import { createResource, getCachedResource } from "frappe-ui";

/** Reads a single field off another record. May return `undefined` synchronously
 *  (e.g. while the fetch is still in flight) — callers fall back. */
export type DocValueReader = (
  doctype: string,
  name: string,
  field: string
) => string | null | undefined;

/**
 * Context for resolving a Currency field's currency code. `doc`/`row`/
 * `defaultCurrency` are plain data the field component supplies; `getDocValue`
 * defaults to the built-in runtime reader (override it in tests, or for an app
 * whose records live in its own store).
 */
export interface CurrencyResolveContext {
  /** The parent doc's values (sibling-field lookup for top-level fields). */
  doc?: Record<string, any> | null;
  /** The child-table row's values, when the field renders as a grid cell. */
  row?: Record<string, any> | null;
  /** Site default currency (`getFormatDefaults().currency`); the final fallback. */
  defaultCurrency?: string | null;
  /** Cross-record reader for the `Doctype:link_field:currency_field` options
   *  form. Defaults to {@link getDocValueReader}. */
  getDocValue?: DocValueReader;
}

// --- Built-in runtime reader -------------------------------------------------

/** Cache namespace for the resources frappe-ui keys by doctype/name/field. */
const CACHE_NS = "FormLayout:field_currency";

/**
 * Built-in reader, backed by frappe-ui's resource cache. On a miss it creates an
 * auto-fetching `createResource` keyed by doctype/name/field; on a hit it reuses
 * the cached one, reading its reactive `.data` so the calling computed re-runs
 * when the fetch lands. Returns `undefined` until then — and always when there's
 * no `window` (headless/SSR/tests never fetch).
 *
 * The `getCachedResource` lookup matters: re-calling `createResource` with the
 * same `cache` key while `auto` is set would `reload()` on every computed re-run
 * (a fetch storm), so the resource is created once and reused thereafter.
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

/** Point the resolver at a different record source (an app's doc store, a test
 *  stub). Pass `null` (or call {@link resetDocValueReader}) to restore the built-in. */
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

/** Row wins over the parent doc; a blank (`undefined`/`null`/`''`) value defers. */
function pickSiblingValue(ctx: CurrencyResolveContext, field: string): any {
  const fromRow = ctx.row?.[field];
  if (fromRow !== undefined && fromRow !== null && fromRow !== "")
    return fromRow;
  return ctx.doc?.[field];
}

/**
 * Resolve a Currency field's currency code from its `options`, mirroring Frappe
 * desk's `frappe.meta.get_field_currency`:
 *
 * 1. **No `options`** → the site default currency.
 * 2. **`options` = a sibling fieldname** → that field's value. In a grid cell the
 *    row's own column wins; otherwise (or when blank) the parent doc. Empty → default.
 * 3. **`options` contains `:`** (`Doctype:link_field:currency_field`) → read the
 *    currency off the linked record. `link_field` (row, else doc) holds that
 *    record's name; `getDocValue` reads `currency_field` off it (built-in reader
 *    by default). Unresolved (record not yet fetched / no value) → default.
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
