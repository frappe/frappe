// Separate, NON-blocking, keyed on `translations_version` (#42070).
//
// Desk v1 already works this way (`www/desk.html:59-70`); CRM regressed it by putting
// `translated_messages` inside `get_boot()`, which forfeits cacheability -- boot
// varies per user and per request, translations vary per language and per build.

let messages: Record<string, string> = {}

export function loadTranslations(version: string, lang = 'en') {
  // `get_boot_translations`, the same endpoint desk v1 uses, and for the same reason:
  // it carries `@http_cache(max_age=31536000)`, so the version in the query string is
  // the only thing that ever invalidates it.
  //
  // Deliberately not awaited by the caller. Untranslated text is a survivable first
  // frame; a missing CSRF token is not.
  return fetch(`/api/method/frappe.translate.get_boot_translations?lang=${lang}&v=${version}`)
    .then((res) => (res.ok ? res.json() : null))
    .then((body) => {
      if (body?.message) messages = body.message
    })
    .catch(() => {
      // A failed translation fetch leaves English on screen. It must never take the
      // shell down with it.
    })
}

export function translate(text: string) {
  return Object.hasOwn(messages, text) ? messages[text] : text
}
