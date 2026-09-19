// Translations: fetched apart from boot, never awaited, keyed on `translations_version`.

import { getTranslations } from '@framework/ui/api'

let messages: Record<string, string> = {}

export function loadTranslations(version: string, lang = 'en') {
  return getTranslations(lang, version)
    .then((response) => {
      if (response.data) messages = response.data
    })
    .catch(() => {
      // A failed fetch leaves English on screen; it must never take the shell down.
    })
}

export function translate(text: string) {
  return Object.hasOwn(messages, text) ? messages[text] : text
}
