import gettext
import os

from babel.messages.mofile import read_mo

import frappe

# Cache keys
MERGED_TRANSLATION_KEY = "merged_translations"
APP_TRANSLATION_KEY = "translations_from_apps"


def get_translator(lang: str, localedir: str | None = "locale", context: bool | None = False):
	t = gettext.translation("messages", localedir=localedir, languages=(lang,), fallback=True)

	if context:
		return t.pgettext

	return t.gettext


def f(msg: str, context: str = None, lang: str = "en"):
	from frappe import as_unicode
	from frappe.utils import is_html, strip_html_tags

	if not lang:
		lang = "en"

	msg = as_unicode(msg).strip()

	if is_html(msg):
		msg = strip_html_tags(msg)

	apps = frappe.get_all_apps()

	for app in apps:
		app_path = frappe.get_pymodule_path(app)
		locale_path = os.path.join(app_path, "locale")
		has_context = context is not None

		if has_context:
			t = get_translator(lang, localedir=locale_path, context=has_context)
			r = t(context, msg)
			if r != msg:
				return r

		t = get_translator(lang, localedir=locale_path, context=False)
		r = t(msg)

		if r != msg:
			return r

	return msg


def get_all_translations(lang: str) -> dict[str, str]:
	if not lang:
		return {}

	def t():
		all_translations = get_translations_from_apps(lang)
		return all_translations

	try:
		return frappe.cache().hget(MERGED_TRANSLATION_KEY, lang, generator=t)
	except:
		# People mistakenly call translation function on global variables where
		# locals are not initialized, translations don't make much sense there
		return {}


def get_translations_from_apps(lang, apps=None):
	if not lang or lang == "en":
		return {}

	def t():
		translations = {}

		for app in apps or frappe.get_all_apps(True):
			app_path = frappe.get_pymodule_path(app)
			localedir = os.path.join(app_path, "locale")
			mo_files = gettext.find("messages", localedir, (lang,), True)

			for file in mo_files:
				with open(file, "rb") as f:
					po = read_mo(f)
					for m in po:
						translations[m.id] = m.string

		return translations

	return frappe.cache().hget(APP_TRANSLATION_KEY, lang, shared=True, generator=t)


def get_messages_for_boot():
	"""
	Return all message translations that are required on boot
	"""
	messages = get_all_translations(frappe.local.lang)

	return messages
