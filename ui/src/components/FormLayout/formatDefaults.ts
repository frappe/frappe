/**
 * Site-default resolver for `FormLayout`'s built-in field components.
 *
 * `FormLayout` is built **in the frappe repo on purpose**: Frappe owns the system
 * defaults (`number_format`, `currency`, `currency_precision`, `float_precision`,
 * `rounding_method`, `date_format`, `time_format` — System Settings + Global
 * Defaults), delivered to the client by desk boot as `window.sysdefaults`
 * (`frappe/boot.py`: `bootinfo.sysdefaults = frappe.defaults.get_defaults()`). So
 * the lib **may assume a Frappe runtime** and read those *framework* defaults
 * directly, shipping field components that format correctly out of the box.
 *
 * This is the single, isolated seam where that assumption lives — every other
 * module (notably the pure `formatNumber.ts`) stays arg-driven and runtime-blind.
 * Two halves:
 *
 * - **Default path:** `getFormatDefaults()` reads `window.sysdefaults`, layered
 *   over lib fallbacks — zero app wiring, site-accurate by default.
 * - **Override seam:** `setFormatDefaults()` lets an app point the lib at a
 *   different source (a session store, a portal/headless context with no boot)
 *   and lets unit tests inject a known site. Mirrors the module-level
 *   `registerFieldType` registry — one seam family, not a new one.
 *
 * **Precedence** (lowest to highest): lib fallback → `window.sysdefaults` →
 * `setFormatDefaults` override. Per-field meta (`field.precision`, currency from
 * `field.options`) beats all of these — resolved by the field component itself,
 * not here. See `plans/PLAN.md` locked decision 6.
 *
 * Framework **data** defaults only. App-specific *behaviour* (Link
 * create/redirect/edit) is out of scope and stays app-supplied via the registry
 * (see `[[formlayout-behaviour-seam-taste]]`).
 */
import { shallowRef } from 'vue'
import { DEFAULT_NUMBER_FORMAT, DEFAULT_ROUNDING_METHOD } from './formatNumber'

/**
 * Framework formatting defaults, keyed to mirror Frappe's `sysdefaults` /
 * `DocField` names (snake_case) so `window.sysdefaults` is a pass-through. Field
 * components translate these to the pure utils' camelCase option args. Date/time
 * keys are carried for the future Date/Datetime/Time fields (which delegate to
 * frappe-ui pickers today and don't read them yet) — shaping the seam now keeps
 * later work additive.
 */
export interface FormatDefaults {
  number_format?: string
  /** ISO currency code, or null/absent when the site has none. */
  currency?: string | null
  currency_precision?: number | string
  float_precision?: number | string
  rounding_method?: string
  date_format?: string
  time_format?: string
}

/** Lib fallbacks — what formatting resolves to with no Frappe boot and no override. */
const LIB_FALLBACK: FormatDefaults = {
  number_format: DEFAULT_NUMBER_FORMAT,
  rounding_method: DEFAULT_ROUNDING_METHOD,
}

/**
 * App/test override, layered on top of the Frappe boot read. **Reactive** (a
 * `shallowRef`) so a `setFormatDefaults()` call after fields have rendered
 * re-triggers any `computed` that resolved its formatting via
 * `getFormatDefaults()` — without it, rendered fields cache stale defaults and
 * "don't change when changed from settings". (The `window.sysdefaults` boot read
 * is static — it's set once at page boot, so picking up new System Settings needs
 * a reload, same as Frappe desk / CRM. In-session changes flow through this ref.)
 */
const override = shallowRef<FormatDefaults>({})

/** Drop `undefined` / `null` / `''` so a blank boot value can't clobber a fallback. */
function defined(o: FormatDefaults): FormatDefaults {
  const out: Record<string, unknown> = {}
  for (const k in o) {
    const v = (o as Record<string, unknown>)[k]
    if (v !== undefined && v !== null && v !== '') out[k] = v
  }
  return out as FormatDefaults
}

/**
 * Read Frappe's boot-delivered defaults. Returns `{}` when there's no `window`
 * (unit tests, SSR, headless) or no `sysdefaults` (portal/Guest boot) — so the
 * lib falls back cleanly rather than throwing.
 */
function readFrappeBoot(): FormatDefaults {
  if (typeof window === 'undefined') return {}
  return ((window as unknown as { sysdefaults?: FormatDefaults }).sysdefaults) ?? {}
}

/**
 * Resolve the active formatting defaults: lib fallback → Frappe boot → app
 * override. Field components call this, then let per-field meta win on top.
 */
export function getFormatDefaults(): FormatDefaults {
  // Reading `override.value` registers the reactive dependency, so a computed
  // that calls this re-runs when `setFormatDefaults` replaces the override.
  return { ...LIB_FALLBACK, ...defined(readFrappeBoot()), ...defined(override.value) }
}

/**
 * Override the framework defaults (merged over prior overrides). For apps whose
 * settings don't live in `window.sysdefaults`, and for tests that need a known
 * site. Pass a partial — unspecified keys keep falling through to boot/fallback.
 */
export function setFormatDefaults(partial: FormatDefaults): void {
  // Assign a fresh object so the shallowRef triggers (mutating in place wouldn't).
  override.value = { ...override.value, ...partial }
}

/** Clear all overrides (test isolation — restores the boot/fallback path). */
export function resetFormatDefaults(): void {
  override.value = {}
}
