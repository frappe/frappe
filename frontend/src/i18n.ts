// Translations: fetched apart from boot, never awaited, keyed on `translations_version`.

let messages: Record<string, string> = {}

export function loadTranslations(version: string, lang = 'en') {
  // Cached server-side for a year; the version in the query string is the only invalidator.
  return fetch(`/api/method/frappe.translate.get_boot_translations?lang=${lang}&v=${version}`)
    .then((res) => (res.ok ? res.json() : null))
    .then((body) => {
      if (body?.message) messages = body.message
    })
    .catch(() => {
      // A failed fetch leaves English on screen; it must never take the shell down.
    })
}

export function translate(text: string) {
  return Object.hasOwn(messages, text) ? messages[text] : text
}
