import csv
import gettext
import os
from collections import defaultdict
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.extract import extract_from_dir
from babel.messages.mofile import read_mo, write_mo
from babel.messages.pofile import read_po, write_po

import frappe
from frappe.translate import get_dict_from_hooks
from frappe.utils import get_bench_path

DEFAULT_LANG = "en"
PO_DIR = "locale"  # po and pot files go into [app]/locale
POT_FILE = "main.pot"  # the app's pot file is always main.pot
MERGED_TRANSLATION_KEY = "gettext_merged_translations"
APP_TRANSLATION_KEY = "gettext_app_translations"
USER_TRANSLATION_KEY = "gettext_user_translations"


def new_catalog(app: str, locale: str | None = None) -> Catalog:
	def get_hook(hook, app):
		return frappe.get_hooks(hook, [None], app)[0]

	app_email = get_hook("app_email", app)
	return Catalog(
		locale=locale,
		domain="messages",
		msgid_bugs_address=app_email,
		language_team=app_email,
		copyright_holder=get_hook("app_publisher", app),
		last_translator=app_email,
		project=get_hook("app_title", app),
		creation_date=datetime.now(),
		revision_date=datetime.now(),
		fuzzy=False,
	)


def get_po_dir(app: str) -> Path:
	return Path(frappe.get_app_path(app)) / PO_DIR


def get_locale_dir() -> Path:
	return Path(get_bench_path()) / "sites" / "assets" / "locale"


def get_locales(app: str) -> list[str]:
	return [locale.stem for locale in get_po_dir(app).iterdir() if locale.suffix == ".po"]


def get_po_path(app: str, locale: str | None = None) -> Path:
	return get_po_dir(app) / f"{locale}.po"


def get_mo_path(app: str, locale: str | None = None) -> Path:
	return get_locale_dir() / locale / "LC_MESSAGES" / f"{app}.mo"


def get_pot_path(app: str) -> Path:
	return get_po_dir(app) / POT_FILE


def get_catalog(app: str, locale: str | None = None) -> Catalog:
	"""Returns a catatalog for the given app and locale"""
	po_path = get_po_path(app, locale) if locale else get_pot_path(app)

	if not po_path.exists():
		return new_catalog(app, locale)

	with open(po_path, "rb") as f:
		return read_po(f)


def write_catalog(app: str, catalog: Catalog, locale: str | None = None) -> Path:
	"""Writes a catalog to the given app and locale"""
	po_path = get_po_path(app, locale) if locale else get_pot_path(app)

	if not po_path.parent.exists():
		po_path.parent.mkdir(parents=True)

	with open(po_path, "wb") as f:
		write_po(f, catalog, sort_output=True, ignore_obsolete=True)

	return po_path


def write_binary(app: str, catalog: Catalog, locale: str) -> Path:
	mo_path = get_mo_path(app, locale)

	if not mo_path.parent.exists():
		mo_path.parent.mkdir(parents=True)

	with open(mo_path, "wb") as mo_file:
		write_mo(mo_file, catalog)

	return mo_path


def generate_pot(target_app: str | None = None):
	"""
	Generate a POT (PO template) file. This file will contain only messages IDs.
	https://en.wikipedia.org/wiki/Gettext
	:param target_app: If specified, limit to `app`
	"""

	def directory_filter(dirpath: str | os.PathLike[str]) -> bool:
		if "public/dist" in dirpath:
			return False

		subdir = os.path.basename(dirpath)
		return not (subdir.startswith(".") or subdir.startswith("_"))

	apps = [target_app] if target_app else frappe.get_all_apps(True)
	method_map = [
		("**.py", "frappe.gettext.extractors.python.extract"),
		("**.js", "frappe.gettext.extractors.javascript.extract"),
		("**/doctype/*/*.json", "frappe.gettext.extractors.doctype.extract"),
		("**/workspace/*/*.json", "frappe.gettext.extractors.workspace.extract"),
		("**.html", "frappe.gettext.extractors.jinja2.extract"),
		("hooks.py", "frappe.gettext.extractors.navbar.extract"),
		("**/report/*/*.json", "frappe.gettext.extractors.report.extract"),
		("**/onboarding_step/*/*.json", "frappe.gettext.extractors.onboarding_step.extract"),
	]

	for app in apps:
		app_path = frappe.get_pymodule_path(app)
		catalog = get_catalog(app)

		for filename, lineno, message, comments, context in extract_from_dir(
			app_path, method_map, directory_filter=directory_filter
		):
			if not message:
				continue

			catalog.add(message, locations=[(filename, lineno)], auto_comments=comments, context=context)

		pot_path = write_catalog(app, catalog)
		print(f"POT file created at {pot_path}")


def new_po(locale, target_app: str | None = None):
	apps = [target_app] if target_app else frappe.get_all_apps(True)

	for target_app in apps:
		po_path = get_po_path(target_app, locale)
		if os.path.exists(po_path):
			print(f"{po_path} exists. Skipping")
			continue

		pot_catalog = get_catalog(target_app)
		pot_catalog.locale = locale
		po_path = write_catalog(target_app, pot_catalog, locale)

		print(f"PO file created_at {po_path}")
		print(
			"You will need to add the language in frappe/geo/languages.json, if you haven't done it already."
		)


def compile(target_app: str | None = None, locale: str | None = None):
	apps = [target_app] if target_app else frappe.get_all_apps(True)

	for app in apps:
		locales = [locale] if locale else get_locales(app)
		for locale in locales:
			catalog = get_catalog(app, locale)
			mo_path = write_binary(app, catalog, locale)
			print(f"MO file created at {mo_path}")


def update_po(target_app: str | None = None, locale: str | None = None):
	"""
	Add keys to available PO files, from POT file. This could be used to keep
	track of available keys, and missing translations
	:param target_app: Limit operation to `app`, if specified
	"""
	apps = [target_app] if target_app else frappe.get_all_apps(True)

	for app in apps:
		locales = [locale] if locale else get_locales(app)
		pot_catalog = get_catalog(app)
		for locale in locales:
			po_catalog = get_catalog(app, locale)
			po_catalog.update(pot_catalog)
			po_path = write_catalog(app, po_catalog, locale)
			print(f"PO file modified at {po_path}")


def migrate(app: str | None = None, locale: str | None = None):
	apps = [app] if app else frappe.get_all_apps(True)

	for app in apps:
		if locale:
			csv_to_po(app, locale)
		else:
			app_path = Path(frappe.get_app_path(app))
			for filename in (app_path / "translations").iterdir():
				if filename.suffix != ".csv":
					continue
				csv_to_po(app, filename.stem)


def csv_to_po(app: str, locale: str):
	csv_file = Path(frappe.get_app_path(app)) / "translations" / f"{locale.replace('_', '-')}.csv"
	locale = locale.replace("-", "_")
	if not csv_file.exists():
		return

	catalog: Catalog = get_catalog(app)
	msgid_context_map = defaultdict(list)
	for message in catalog:
		msgid_context_map[message.id].append(message.context)

	with open(csv_file) as f:
		for row in csv.reader(f):
			if len(row) < 2:
				continue

			msgid = escape_percent(row[0])
			msgstr = escape_percent(row[1])
			msgctxt = row[2] if len(row) >= 3 else None

			if not msgctxt:
				# if old context is not defined, add msgstr to all contexts
				for context in msgid_context_map.get(msgid, []):
					if message := catalog.get(msgid, context):
						message.string = msgstr
			elif message := catalog.get(msgid, msgctxt):
				message.string = msgstr

	po_path = write_catalog(app, catalog, locale)
	print(f"PO file created at {po_path}")


def get_messages_for_boot():
	"""
	Return all message translations that are required on boot
	"""
	messages = get_all_translations(frappe.local.lang)
	messages.update(get_dict_from_hooks("boot", None))

	return messages


def make_dict_from_messages(messages, full_dict=None, load_user_translation=True):
	"""Returns translated messages as a dict in Language specified in `frappe.local.lang`
	:param messages: List of untranslated messages
	"""
	out = {}
	if full_dict is None:
		if load_user_translation:
			full_dict = get_all_translations(frappe.local.lang)
		else:
			full_dict = get_translations_from_apps(frappe.local.lang)

	for m in messages:
		if m[1] in full_dict:
			out[m[1]] = full_dict[m[1]]
		# check if msg with context as key exist eg. msg:context
		if len(m) > 2 and m[2]:
			key = m[1] + ":" + m[2]
			if full_dict.get(key):
				out[key] = full_dict[key]

	return out


def get_all_translations(lang: str) -> dict[str, str]:
	"""
	Load and return the entire translations dictionary for a language from apps
	+ user translations.
	:param lang: Language Code, e.g. `hi`
	:return: dictionary of key and value
	"""
	if not lang:
		return {}

	def t():
		all_translations = get_translations_from_apps(lang)
		with suppress(Exception):
			# get user specific translation data
			user_translations = get_user_translations(lang)
			all_translations.update(user_translations)

		return all_translations

	try:
		return frappe.cache().hget(MERGED_TRANSLATION_KEY, lang, generator=t)
	except Exception:
		# People mistakenly call translation function on global variables where
		# locals are not initialized, translations don't make much sense there
		return {}


def get_translations_from_apps(lang, apps=None):
	"""
	Combine translations from installed apps.

	For dialects (i.e. es_GT), take translations from the base language (i.e. es)
	and then update with specific translations from the dialect (i.e. es_GT).

	If we only have a translation with context, also use it as a translation
	without context. This way we can provide the context for each source string
	but don't have to create a translation for each context.
	"""
	if not lang or lang == DEFAULT_LANG:
		return {}

	def t():
		translations = {}

		locale_dir = get_locale_dir()
		for app in apps or frappe.get_installed_apps():
			mo_files = gettext.find(app, locale_dir, (lang,), True)
			for file in mo_files:
				with open(file, "rb") as f:
					catalog = read_mo(f)
					for m in catalog:
						if not m.id:
							continue

						key = m.id
						if m.context:
							context = m.context.decode()  # context is encoded as bytes
							translations[f"{key}:{context}"] = m.string
							if m.id not in translations:
								# better a translation with context than no translation
								translations[m.id] = m.string
						else:
							translations[m.id] = m.string

		return translations

	return frappe.cache().hget(APP_TRANSLATION_KEY, lang, shared=True, generator=t)


def get_user_translations(lang: str) -> dict[str, str]:
	"""
	Get translations from db, created by user
	:param lang: language to fetch
	:return: translation key/value
	"""
	if not frappe.db:
		frappe.connect()

	def f():
		user_translations = {}
		translations = frappe.get_all(
			"Translation",
			fields=["source_text", "translated_text", "context"],
			filters={"language": lang},
		)

		for t in translations:
			key = t.source_text
			value = t.translated_text
			if t.context:
				key += f":{t.context}"
			user_translations[key] = value

		return user_translations

	return frappe.cache().hget(USER_TRANSLATION_KEY, lang, generator=f)


def clear_cache():
	"""Clear all translation assets from :meth:`frappe.cache`"""
	cache = frappe.cache()
	cache.delete_key("langinfo")

	# clear translations saved in boot cache
	cache.delete_key("bootinfo")
	cache.delete_key("translation_assets", shared=True)
	cache.delete_key(APP_TRANSLATION_KEY, shared=True)
	cache.delete_key(USER_TRANSLATION_KEY)
	cache.delete_key(MERGED_TRANSLATION_KEY)


def escape_percent(s: str):
	return s.replace("%", "&#37;")
