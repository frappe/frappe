import csv
import gettext
import multiprocessing
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.extract import DEFAULT_KEYWORDS, extract_from_dir
from babel.messages.mofile import read_mo, write_mo
from babel.messages.pofile import read_po, write_po

import frappe
from frappe.utils import get_bench_path

PO_DIR = "locale"  # po and pot files go into [app]/locale
POT_FILE = "main.pot"  # the app's pot file is always main.pot


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
	po_dir = get_po_dir(app)
	if not po_dir.exists():
		return []

	return [locale.stem for locale in po_dir.iterdir() if locale.suffix == ".po"]


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
		write_po(f, catalog, sort_output=True, ignore_obsolete=True, width=None)

	return po_path


def write_binary(app: str, catalog: Catalog, locale: str) -> Path:
	mo_path = get_mo_path(app, locale)

	if not mo_path.parent.exists():
		mo_path.parent.mkdir(parents=True)

	with open(mo_path, "wb") as mo_file:
		write_mo(mo_file, catalog)

	return mo_path


def get_method_map(app: str):
	file_path = Path(frappe.get_app_path(app)).parent / "babel_extractors.csv"
	if file_path.exists():
		with open(file_path) as f:
			reader = csv.reader(f)
			return [(row[0], row[1]) for row in reader]

	return []


def generate_pot(target_app: str | None = None):
	"""
	Generate a POT (PO template) file. This file will contain only messages IDs.
	https://en.wikipedia.org/wiki/Gettext
	:param target_app: If specified, limit to `app`
	"""

	is_gitignored = get_is_gitignored_function_for_app(target_app)

	def directory_filter(dirpath: str | os.PathLike[str]) -> bool:
		if is_gitignored(str(dirpath)):
			return False

		subdir = os.path.basename(dirpath)
		return not (subdir.startswith(".") or subdir.startswith("_"))

	apps = [target_app] if target_app else frappe.get_all_apps(True)
	default_method_map = get_method_map("frappe")

	keywords = DEFAULT_KEYWORDS.copy()
	keywords["_lt"] = None

	for app in apps:
		app_path = frappe.get_pymodule_path(app, "..")
		catalog = new_catalog(app)

		# Each file will only be processed by the first method that matches,
		# so more specific methods should come first.
		method_map = [] if app == "frappe" else get_method_map(app)
		method_map.extend(default_method_map)

		for filename, lineno, message, comments, context in extract_from_dir(
			app_path, method_map, directory_filter=directory_filter, keywords=keywords
		):
			if not message:
				continue

			catalog.add(message, locations=[(filename, lineno)], auto_comments=comments, context=context)

		pot_path = write_catalog(app, catalog)
		print(f"POT file created at {pot_path}")


def get_is_gitignored_function_for_app(app: str | None):
	"""
	Used to check if a directory is gitignored or not.
	Can NOT be used to check if a file is gitignored or not.
	"""
	import git

	if not app:
		return lambda d: "public/dist" in d

	repo = git.Repo(frappe.get_app_source_path(app), search_parent_directories=True)

	def _check_gitignore(d: str):
		d = d.rstrip("/")
		if repo.ignored([d]):  # type: ignore
			return True
		return False

	return _check_gitignore


def new_po(locale, target_app: str | None = None):
	apps = [target_app] if target_app else frappe.get_all_apps(True)

	for app in apps:
		po_path = get_po_path(app, locale)
		if os.path.exists(po_path):
			print(f"{po_path} exists. Skipping")
			continue

		pot_catalog = get_catalog(app)
		pot_catalog.locale = locale
		po_path = write_catalog(app, pot_catalog, locale)

		print(f"PO file created_at {po_path}")
		print(
			"You will need to add the language in frappe/geo/languages.csv, if you haven't done it already."
		)


def compile_translations(target_app: str | None = None, locale: str | None = None, force=False):
	apps = [target_app] if target_app else frappe.get_all_apps(True)
	tasks = []
	for app in apps:
		locales = [locale] if locale else get_locales(app)
		for current_locale in locales:
			tasks.append((app, current_locale, force))

	# Execute all tasks, doing this sequentially is quite slow hence use processpool of 4
	# processes.
	executer = multiprocessing.Pool(processes=4)
	executer.starmap(_compile_translation, tasks)

	executer.close()
	executer.join()


def _compile_translation(app, locale, force=False):
	po_path = get_po_path(app, locale)
	mo_path = get_mo_path(app, locale)
	if not po_path.exists():
		return

	if mo_path.exists() and po_path.stat().st_mtime < mo_path.stat().st_mtime and not force:
		print(f"MO file already up to date at {mo_path}")
		return

	with open(po_path, "rb") as f:
		catalog = read_po(f)

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
			po_catalog.update(pot_catalog, no_fuzzy_matching=True)
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


def get_translations_from_mo(lang, app):
	"""Get translations from MO files.

	For dialects (i.e. es_GT), take translations from the base language (i.e. es)
	and then update with specific translations from the dialect (i.e. es_GT).

	If we only have a translation with context, also use it as a translation
	without context. This way we can provide the context for each source string
	but don't have to create a translation for each context.
	"""
	if not lang or not app:
		return {}

	translations = {}
	lang = lang.replace("-", "_")  # Frappe uses dash, babel uses underscore.

	locale_dir = get_locale_dir()
	mo_file = gettext.find(app, locale_dir, (lang,))
	if not mo_file:
		return translations
	with open(mo_file, "rb") as f:
		catalog = read_mo(f)
		for m in catalog:
			if not m.id:
				continue

			key = m.id
			if m.context:
				context = m.context.decode()  # context is encoded as bytes
				translations[f"{key}:{context}"] = m.string
			else:
				translations[m.id] = m.string
	return translations


def escape_percent(s: str):
	return s.replace("%", "&#37;")
