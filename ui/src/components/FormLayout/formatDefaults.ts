/**
 * Site-default resolver for `FormLayout`'s field components: lib fallback → the session's
 * `defaults` → `setFormatDefaults` override. Per-field meta beats all three.
 */
import { shallowRef } from "vue";
import { currentSession } from "../../composables/useSession";
import { DEFAULT_NUMBER_FORMAT, DEFAULT_ROUNDING_METHOD } from "./formatNumber";

/** snake_case to mirror Frappe's own names, so the session's `defaults` passes straight through. */
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

/** Lib fallbacks — what formatting resolves to with no session and no override. */
const LIB_FALLBACK: FormatDefaults = {
  number_format: DEFAULT_NUMBER_FORMAT,
  rounding_method: DEFAULT_ROUNDING_METHOD,
};

/**
 * App/test override, layered over the session read. Reactive so a `setFormatDefaults()`
 * after fields render re-triggers the computeds that read `getFormatDefaults()`.
 */
const override = shallowRef<FormatDefaults>({});

/** Drop `undefined` / `null` / `''` so a blank session value can't clobber a fallback. */
function defined(o: FormatDefaults): FormatDefaults {
  const out: Record<string, unknown> = {};
  for (const k in o) {
    const v = (o as Record<string, unknown>)[k];
    if (v !== undefined && v !== null && v !== "") out[k] = v;
  }
  return out as FormatDefaults;
}

/** Read the session's site defaults; `{}` with no session so the lib falls back cleanly. */
function readSessionDefaults(): FormatDefaults {
  return (currentSession()?.defaults as FormatDefaults | undefined) ?? {};
}

/** Resolve active defaults: lib fallback → session → app override. */
export function getFormatDefaults(): FormatDefaults {
  // Reading `override.value` registers the reactive dep so callers re-run on override change.
  return {
    ...LIB_FALLBACK,
    ...defined(readSessionDefaults()),
    ...defined(override.value),
  };
}

/**
 * Override the framework defaults (merged over prior overrides). Unspecified keys
 * keep falling through to the session/fallback.
 */
export function setFormatDefaults(partial: FormatDefaults): void {
  // Fresh object so the shallowRef triggers (mutating in place wouldn't).
  override.value = { ...override.value, ...partial };
}

/** Clear all overrides (test isolation — restores the session/fallback path). */
export function resetFormatDefaults(): void {
  override.value = {};
}
