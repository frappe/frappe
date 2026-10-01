// Translations: fetched apart from boot, never awaited, keyed on `translations_version`.
// `__` and `__n` reach stored scripts as `frappe/i18n`; `loadTranslations` stays the shell's.

import { shallowRef, type App } from "vue";
import { getTranslations } from "@framework/ui/api";

type Replacements = (string | number)[];

// A ref, so a template that calls `__` re-renders when the fetch lands after first paint.
const messages = shallowRef<Record<string, string>>({});

export function loadTranslations(version: string, lang = "en") {
  return getTranslations(lang, version)
    .then((response) => {
      if (response.data) messages.value = response.data;
    })
    .catch(() => {
      // A failed fetch leaves English on screen; it must never take the shell down.
    });
}

/** Desk v1's shape: `text:context`, then `text`, then the key itself; `{0}` fills by position. */
export function __(
  text: string,
  replacements?: Replacements | null,
  context?: string | null,
): string {
  if (typeof text !== "string") return text;
  return format(lookup(text, context), replacements);
}

/** Reserved for plural catalogs the framework does not have yet: the English form by `count === 1`. */
export function __n(
  singular: string,
  plural: string,
  count: number,
  replacements?: Replacements | null,
  context?: string | null,
): string {
  return __(count === 1 ? singular : plural, replacements, context);
}

declare module "vue" {
  interface ComponentCustomProperties {
    __: typeof __;
    __n: typeof __n;
  }
}

/** Puts both in every component template with no import; a `setup()` return of the same name wins. */
export function installTranslate(app: App) {
  app.config.globalProperties.__ = __;
  app.config.globalProperties.__n = __n;
}

function lookup(text: string, context?: string | null) {
  const catalog = messages.value;
  const keyed = `${text}:${context}`;
  if (context && Object.hasOwn(catalog, keyed)) return catalog[keyed];
  return Object.hasOwn(catalog, text) ? catalog[text] : text;
}

function format(text: string, replacements?: Replacements | null) {
  if (!replacements) return text;
  return text.replace(/\{(\d+)\}/g, (placeholder, index) => {
    const value = replacements[Number(index)];
    return value === undefined ? placeholder : String(value);
  });
}
