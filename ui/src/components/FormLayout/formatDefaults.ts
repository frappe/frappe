/**
 * Site-default resolver for `FormLayout`'s built-in field components. The single
 * seam that assumes a Frappe runtime: reads framework defaults from desk boot's
 * `window.sysdefaults` (`frappe/boot.py: frappe.defaults.get_defaults()`).
 *
 * Precedence (lowest to highest): lib fallback → `window.sysdefaults` →
 * `setFormatDefaults` override. Per-field meta beats all of these, resolved by
 * the field component itself. Framework data defaults only.
 */
import { shallowRef } from "vue";
import { DEFAULT_NUMBER_FORMAT, DEFAULT_ROUNDING_METHOD } from "./formatNumber";

/**
 * Framework formatting defaults, keyed in snake_case to mirror Frappe's
 * `sysdefaults` / `DocField` names so `window.sysdefaults` is a pass-through.
 * Date/time keys are unused today (Date/Time fields delegate to frappe-ui
 * pickers) but carried so adding them later stays additive.
 */
export interface FormatDefaults {
  number_format?: string;
  /** ISO currency code, or null/absent when the site has none. */
  currency?: string | null;
  currency_precision?: number | string;
  float_precision?: number | string;
  rounding_method?: string;
  date_format?: string;
  time_format?: string;
}

/** Lib fallbacks — what formatting resolves to with no Frappe boot and no override. */
const LIB_FALLBACK: FormatDefaults = {
  number_format: DEFAULT_NUMBER_FORMAT,
  rounding_method: DEFAULT_ROUNDING_METHOD,
};

/**
 * App/test override, layered over the Frappe boot read. Reactive (`shallowRef`)
 * so a `setFormatDefaults()` after fields render re-triggers computeds that read
 * `getFormatDefaults()` — otherwise rendered fields keep stale defaults. (The
 * `window.sysdefaults` boot read is static; new System Settings need a reload,
 * same as desk/CRM.)
 */
const override = shallowRef<FormatDefaults>({});

/** Drop `undefined` / `null` / `''` so a blank boot value can't clobber a fallback. */
function defined(o: FormatDefaults): FormatDefaults {
  const out: Record<string, unknown> = {};
  for (const k in o) {
    const v = (o as Record<string, unknown>)[k];
    if (v !== undefined && v !== null && v !== "") out[k] = v;
  }
  return out as FormatDefaults;
}

/** Read boot-delivered defaults; `{}` with no `window` or no `sysdefaults` so
 *  the lib falls back cleanly. */
function readFrappeBoot(): FormatDefaults {
  if (typeof window === "undefined") return {};
  return (
    (window as unknown as { sysdefaults?: FormatDefaults }).sysdefaults ?? {}
  );
}

/** Resolve active defaults: lib fallback → Frappe boot → app override. */
export function getFormatDefaults(): FormatDefaults {
  // Reading `override.value` registers the reactive dep so callers re-run on override change.
  return {
    ...LIB_FALLBACK,
    ...defined(readFrappeBoot()),
    ...defined(override.value),
  };
}

/**
 * Override the framework defaults (merged over prior overrides). Unspecified keys
 * keep falling through to boot/fallback.
 */
export function setFormatDefaults(partial: FormatDefaults): void {
  // Fresh object so the shallowRef triggers (mutating in place wouldn't).
  override.value = { ...override.value, ...partial };
}

/** Clear all overrides (test isolation — restores the boot/fallback path). */
export function resetFormatDefaults(): void {
  override.value = {};
}
