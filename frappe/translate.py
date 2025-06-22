# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
frappe.translate
~~~~~~~~~~~~~~~~

Translation tools for frappe
"""

import functools
import io
import itertools
import json
import operator
import os
import re
from contextlib import contextmanager, suppress
from csv import reader, writer

import frappe
from frappe.query_builder import DocType, Field
from frappe.utils import cstr, get_bench_path, is_html, strip, strip_html_tags, unique

REPORT_TRANSLATE_PATTERN = re.compile('"([^:,^"]*):')
CSV_STRIP_WHITESPACE_PATTERN = re.compile(r"{\s?([0-9]+)\s?}")


# Cache keys
MERGED_TRANSLATION_KEY = "merged_translations"
USER_TRANSLATION_KEY = "lang_user_translations"


def get_language(lang_list: list | None = None) -> str:
	"""Set `frappe.local.lang` from HTTP headers at beginning of request

	Order of priority for setting language:
	1. Form Dict => _lang
	2. Cookie => preferred_language (Non authorized user)
	3. Request Header => Accept-Language (Non authorized user)
	4. User document => language
	5. System Settings => language
	"""
	is_logged_in = frappe.session.user != "Guest"

	# fetch language from form_dict
	if frappe.form_dict._lang:
		language = get_lang_code(frappe.form_dict._lang or get_parent_language(frappe.form_dict._lang))
		if language:
			return language

	# use language set in User or System Settings if user is logged in
	if is_logged_in:
		return frappe.local.lang

	lang_set = set(lang_list or get_all_languages() or [])

	# fetch language from cookie
	preferred_language_cookie = get_preferred_language_cookie()

	if preferred_language_cookie:
		if preferred_language_cookie in lang_set:
			return preferred_language_cookie

		parent_language = get_parent_language(preferred_language_cookie)
		if parent_language in lang_set:
			return parent_language

	# fetch language from request headers
	accept_language = list(frappe.request.accept_languages.values())

	for language in accept_language:
		if language in lang_set:
			return language

		parent_language = get_parent_language(language)
		if parent_language in lang_set:
			return parent_language

	# fallback to language set in System Settings or "en"
	return frappe.get_system_settings("language") or "en"


@functools.lru_cache
def get_parent_language(lang: str) -> str:
	"""If the passed language is a variant, return its parent

	Eg:
	        1. zh-TW -> zh
	        2. sr-BA -> sr
	"""
	for sep in ("_", "-"):
		if sep in lang:
			return lang.split(sep)[0]


def get_user_lang(user: str | None = None) -> str:
	"""Set frappe.local.lang from user preferences on session beginning or resumption"""
	user = user or frappe.session.user

	# User.language => Session Defaults => frappe.local.lang => 'en'
	return (
		frappe.get_cached_value("User", user, "language")
		or frappe.get_system_settings("language")
		or frappe.local.lang
		or "en"
	)


def get_lang_code(lang: str) -> str | None:
	return frappe.db.get_value("Language", {"name": lang}) or frappe.db.get_value(
		"Language", {"language_name": lang}
	)


def set_default_language(lang):
	"""Set Global default language"""
	if frappe.db.get_default("lang") != lang:
		frappe.db.set_default("lang", lang)
	frappe.local.lang = lang


def get_lang_dict():
	"""Return all languages in dict format, full name is the key e.g. `{"english":"en"}`."""
	return dict(
		frappe.get_all("Language", fields=["language_name", "name"], order_by="creation", as_list=True)
	)


def get_messages_for_boot():
	"""Return all message translations that are required on boot."""

	return get_all_translations(frappe.local.lang)


@frappe.whitelist(allow_guest=True)
def get_app_translations():
	if frappe.session.user != "Guest":
		language = frappe.db.get_value("User", frappe.session.user, "language")
	else:
		language = frappe.db.get_single_value("System Settings", "language")

	return get_all_translations(language)


def get_all_translations(lang: str) -> dict[str, str]:
	"""Load and return the entire translations dictionary for a language from apps + user translations.

	:param lang: Language Code, e.g. `hi` or `es-CO`
	"""
	if not lang:
		return {}

	def _merge_translations():
		from frappe.geo.country_info import get_translated_countries

		parent_lang = get_parent_language(lang)

		# Get translations for parent language
		all_translations = get_translations_from_apps(parent_lang).copy() if parent_lang else {}

		# Update with child language translations (overriding parent translations)
		all_translations.update(get_translations_from_apps(lang))

		with suppress(Exception):
			# Get translations for parent language
			all_translations.update(get_user_translations(parent_lang) if parent_lang else {})
			# Update with child language translations (overriding parent translations)
			all_translations.update(get_user_translations(lang))
			all_translations.update(get_translated_countries())

		return all_translations

	try:
		return frappe.cache.hget(MERGED_TRANSLATION_KEY, lang, generator=_merge_translations)
	except Exception:
		# People mistakenly call translation function on global variables
		# where locals are not initialized, translations don't make much sense there
		frappe.logger().error("Unable to load translations", exc_info=True)
		return {}


def get_translations_from_apps(lang, apps=None):
	"""Combine all translations from `.csv` files in all `apps`.
	For derivative languages (es-GT), take translations from the
	base language (es) and then update translations from the child (es-GT)"""
	translations = {}
	from frappe.gettext.translate import get_translations_from_mo

	for app in apps or frappe.get_installed_apps(_ensure_on_bench=True):
		translations.update(get_translations_from_csv(lang, app) or {})
		translations.update(get_translations_from_mo(lang, app) or {})
	if parent := get_parent_language(lang):
		parent_translations = get_translations_from_apps(parent, apps)
		parent_translations.update(translations)
		return parent_translations

	return translations


def get_translations_from_csv(lang, app):
	return get_translation_dict_from_file(
		os.path.join(frappe.get_app_path(app, "translations"), lang + ".csv"), lang, app
	)


def get_translation_dict_from_file(path, lang, app, throw=False) -> dict[str, str]:
	"""Return translation dict from given CSV file at path"""
	translation_map = {}
	if os.path.exists(path):
		csv_content = read_csv_file(path)

		for item in csv_content:
			if len(item) == 3 and item[2]:
				key = item[0] + ":" + item[2]
				translation_map[key] = strip(item[1])
			elif len(item) in [2, 3]:
				translation_map[item[0]] = strip(item[1])
			elif item:
				msg = f"Bad translation in '{app}' for language '{lang}': {cstr(item)}"
				frappe.log_error(message=msg, title="Error in translation file")
				if throw:
					frappe.throw(msg, title="Error in translation file")

	return translation_map


def get_user_translations(lang):
	def _read_from_db():
		user_translations = {}
		translations = frappe.get_all(
			"Translation", fields=["source_text", "translated_text", "context"], filters={"language": lang}
		)

		for t in translations:
			key = t.source_text
			value = t.translated_text
			if t.context:
				key += ":" + t.context
			user_translations[key] = value
		return user_translations

	return frappe.cache.hget(USER_TRANSLATION_KEY, lang, generator=_read_from_db)


def clear_cache():
	"""Clear all translation assets from :meth:`frappe.cache`"""
	frappe.cache.delete_value(
		keys=["bootinfo", USER_TRANSLATION_KEY, MERGED_TRANSLATION_KEY],
	)


def get_messages_for_app(app, deduplicate=True):
	"""Return all messages (list) for a specified `app`."""
	messages = []
	modules = [frappe.unscrub(m) for m in frappe.local.app_modules[app]]

	# doctypes
	if modules:
		if isinstance(modules, str):
			modules = [modules]
		filtered_doctypes = (
			frappe.qb.from_("DocType").where(Field("module").isin(modules)).select("name").run(pluck=True)
		)
		for name in filtered_doctypes:
			messages.extend(get_messages_from_doctype(name))

		# pages
		filtered_pages = (
			frappe.qb.from_("Page").where(Field("module").isin(modules)).select("name", "title").run()
		)
		for name, title in filtered_pages:
			messages.append((None, title or name))
			messages.extend(get_messages_from_page(name))

		# reports
		report = DocType("Report")
		doctype = DocType("DocType")
		names = (
			frappe.qb.from_(doctype)
			.from_(report)
			.where((report.ref_doctype == doctype.name) & doctype.module.isin(modules))
			.select(report.name)
			.run(pluck=True)
		)
		for name in names:
			messages.append((None, name))
			messages.extend(get_messages_from_report(name))
			for i in messages:
				if not isinstance(i, tuple):
					raise Exception

	# workflow based on app.hooks.fixtures
	messages.extend(get_messages_from_workflow(app_name=app))

	# custom fields based on app.hooks.fixtures
	messages.extend(get_messages_from_custom_fields(app_name=app))

	# app_include_files
	messages.extend(get_all_messages_from_js_files(app))

	# server_messages
	messages.extend(get_server_messages(app))

	# messages from navbar settings
	messages.extend(get_messages_from_navbar())

	if deduplicate:
		messages = deduplicate_messages(messages)

	return messages


def get_messages_from_navbar():
	"""Return all labels from Navbar Items, as specified in Navbar Settings."""
	labels = frappe.get_all("Navbar Item", filters={"item_label": ("is", "set")}, pluck="item_label")
	return [("Navbar:", label, "Label of a Navbar Item") for label in labels]


def get_messages_from_doctype(name):
	"""Extract all translatable messages for a doctype. Includes labels, Python code,
	Javascript code, html templates"""
	from frappe.gettext.extractors.utils import is_translatable

	messages = []
	meta = frappe.get_meta(name)

	messages = [meta.name, meta.module]

	if meta.description:
		messages.append(meta.description)

	# translations of field labels, description and options
	for d in meta.get("fields"):
		messages.extend([d.label, d.description])

		if d.fieldtype == "Select" and d.options:
			options = d.options.split("\n")
			if "icon" not in options[0]:
				messages.extend(options)
		if d.fieldtype == "HTML" and d.options:
			messages.append(d.options)

	# translations of roles
	messages.extend(d.role for d in meta.get("permissions") if d.role)
	messages = [message for message in messages if message]
	messages = [("DocType: " + name, message) for message in messages if is_translatable(message)]

	# extract from js, py files
	if not meta.custom:
		doctype_file_path = frappe.get_module_path(meta.module, "doctype", meta.name, meta.name)
		messages.extend(get_messages_from_file(doctype_file_path + ".js"))
		messages.extend(get_messages_from_file(doctype_file_path + "_list.js"))
		messages.extend(get_messages_from_file(doctype_file_path + "_list.html"))
		messages.extend(get_messages_from_file(doctype_file_path + "_calendar.js"))
		messages.extend(get_messages_from_file(doctype_file_path + "_dashboard.html"))

	# workflow based on doctype
	messages.extend(get_messages_from_workflow(doctype=name))
	return messages


def get_messages_from_workflow(doctype=None, app_name=None):
	assert doctype or app_name, "doctype or app_name should be provided"
	from frappe.gettext.extractors.utils import is_translatable

	# translations for Workflows
	workflows = []
	if doctype:
		workflows = frappe.get_all("Workflow", filters={"document_type": doctype})
	else:
		fixtures = frappe.get_hooks("fixtures", app_name=app_name) or []
		for fixture in fixtures:
			if isinstance(fixture, str) and fixture == "Workflow":
				workflows = frappe.get_all("Workflow")
				break
			elif isinstance(fixture, dict) and fixture.get("dt", fixture.get("doctype")) == "Workflow":
				workflows.extend(frappe.get_all("Workflow", filters=fixture.get("filters")))

	messages = []
	document_state = DocType("Workflow Document State")
	for w in workflows:
		states = frappe.db.get_values(
			document_state,
			filters=document_state.parent == w["name"],
			fieldname="state",
			distinct=True,
			as_dict=True,
			order_by=None,
		)
		messages.extend(
			[
				("Workflow: " + w["name"], state["state"])
				for state in states
				if is_translatable(state["state"])
			]
		)
		states = frappe.db.get_values(
			document_state,
			filters=(document_state.parent == w["name"]) & (document_state.message.isnotnull()),
			fieldname="message",
			distinct=True,
			order_by=None,
			as_dict=True,
		)
		messages.extend(
			[
				("Workflow: " + w["name"], state["message"])
				for state in states
				if is_translatable(state["message"])
			]
		)

		actions = frappe.db.get_values(
			"Workflow Transition",
			filters={"parent": w["name"]},
			fieldname="action",
			as_dict=True,
			distinct=True,
			order_by=None,
		)

		messages.extend(
			[
				("Workflow: " + w["name"], action["action"])
				for action in actions
				if is_translatable(action["action"])
			]
		)

	return messages


def get_messages_from_custom_fields(app_name):
	from frappe.gettext.extractors.utils import is_translatable

	fixtures = frappe.get_hooks("fixtures", app_name=app_name) or []
	custom_fields = []

	for fixture in fixtures:
		if isinstance(fixture, str) and fixture == "Custom Field":
			custom_fields = frappe.get_all(
				"Custom Field", fields=["name", "label", "description", "fieldtype", "options"]
			)
			break
		elif isinstance(fixture, dict) and fixture.get("dt", fixture.get("doctype")) == "Custom Field":
			custom_fields.extend(
				frappe.get_all(
					"Custom Field",
					filters=fixture.get("filters"),
					fields=["name", "label", "description", "fieldtype", "options"],
				)
			)

	messages = []
	for cf in custom_fields:
		for prop in ("label", "description"):
			if not cf.get(prop) or not is_translatable(cf[prop]):
				continue
			messages.append(("Custom Field - {}: {}".format(prop, cf["name"]), cf[prop]))
		if cf["fieldtype"] == "Selection" and cf.get("options"):
			messages.extend(
				("Custom Field - Description: " + cf["name"], option)
				for option in cf["options"].split("\n")
				if option and "icon" not in option and is_translatable(option)
			)
	return messages


def get_messages_from_page(name):
	"""Return all translatable strings from a :class:`frappe.core.doctype.Page`."""
	return _get_messages_from_page_or_report("Page", name)


def get_messages_from_report(name):
	"""Return all translatable strings from a :class:`frappe.core.doctype.Report`."""
	from frappe.gettext.extractors.utils import is_translatable

	report = frappe.get_doc("Report", name)
	messages = _get_messages_from_page_or_report(
		"Report", name, frappe.db.get_value("DocType", report.ref_doctype, "module")
	)

	if report.columns:
		context = "Column of report '{}'".format(
			report.name
		)  # context has to match context in `prepare_columns` in query_report.js
		messages.extend([(None, report_column.label, context) for report_column in report.columns])

	if report.filters:
		messages.extend([(None, report_filter.label) for report_filter in report.filters])

	if report.query:
		messages.extend(
			[
				(None, message)
				for message in REPORT_TRANSLATE_PATTERN.findall(report.query)
				if is_translatable(message)
			]
		)

	messages.append((None, report.report_name))
	return messages


def _get_messages_from_page_or_report(doctype, name, module=None):
	if not module:
		module = frappe.db.get_value(doctype, name, "module")

	doc_path = frappe.get_module_path(module, doctype, name)

	messages = get_messages_from_file(os.path.join(doc_path, frappe.scrub(name) + ".py"))

	if os.path.exists(doc_path):
		for filename in os.listdir(doc_path):
			if filename.endswith(".js") or filename.endswith(".html"):
				messages += get_messages_from_file(os.path.join(doc_path, filename))

	return messages


def get_server_messages(app):
	"""Extracts all translatable strings (tagged with :func:`frappe._`) from Python modules
	inside an app"""
	messages = []
	file_extensions = (".py", ".html", ".js", ".vue")
	app_walk = os.walk(frappe.get_app_path(app))

	for basepath, folders, files in app_walk:
		folders[:] = [folder for folder in folders if folder not in {".git", "__pycache__"}]

		if "public/dist" in basepath:
			continue

		for f in files:
			f = frappe.as_unicode(f)
			if f.endswith(file_extensions):
				messages.extend(get_messages_from_file(os.path.join(basepath, f)))

	return messages


def get_messages_from_include_files(app_name=None):
	"""Return messages from js files included at time of boot like desk.min.js for desk and web."""
	from frappe.utils.jinja_globals import bundled_asset

	messages = []
	app_include_js = frappe.get_hooks("app_include_js", app_name=app_name) or []
	web_include_js = frappe.get_hooks("web_include_js", app_name=app_name) or []
	include_js = app_include_js + web_include_js

	for js_path in include_js:
		file_path = bundled_asset(js_path)
		relative_path = os.path.join(frappe.local.sites_path, file_path.lstrip("/"))
		messages_from_file = get_messages_from_file(relative_path)
		messages.extend(messages_from_file)

	return messages


def get_all_messages_from_js_files(app_name=None):
	"""Extracts all translatable strings from app `.js` files"""
	messages = []
	for app in [app_name] if app_name else frappe.get_installed_apps(_ensure_on_bench=True):
		if os.path.exists(frappe.get_app_path(app, "public")):
			for basepath, folders, files in os.walk(frappe.get_app_path(app, "public")):  # noqa: B007
				if "frappe/public/js/lib" in basepath:
					continue

				for fname in files:
					if fname.endswith(".js") or fname.endswith(".html") or fname.endswith(".vue"):
						messages.extend(get_messages_from_file(os.path.join(basepath, fname)))

	return messages


def get_messages_from_file(path: str) -> list[tuple[str, str, str | None, int]]:
	"""Return a list of transatable strings from a code file.

	:param path: path of the code file
	"""

	from frappe.gettext.extractors.utils import extract_messages_from_code

	frappe.flags.setdefault("scanned_files", set())
	# TODO: Find better alternative
	# To avoid duplicate scan
	if path in frappe.flags.scanned_files:
		return []

	frappe.flags.scanned_files.add(path)

	bench_path = get_bench_path()
	if not os.path.exists(path):
		return []

	with open(path) as sourcefile:
		try:
			file_contents = sourcefile.read()
		except Exception:
			print(f"Could not scan file for translation: {path}")
			return []

		messages = []

		if path.lower().endswith(".py"):
			messages += extract_messages_from_python_code(file_contents)
		else:
			messages += extract_messages_from_code(file_contents)

		if path.lower().endswith(".js"):
			# For JS also use JS parser to extract strings possibly missed out
			# by regex based extractor.
			messages += extract_messages_from_javascript_code(file_contents)

		return [
			(os.path.relpath(path, bench_path), message, context, line)
			for (line, message, context) in messages
		]


def extract_messages_from_python_code(code: str) -> list[tuple[int, str, str | None]]:
	"""Extracts translatable strings from Python code using babel."""
	from babel.messages.extract import extract_python

	messages = []

	for message in extract_python(
		io.BytesIO(code.encode()),
		keywords=["_", "_lt"],
		comment_tags=(),
		options={},
	):
		lineno, _func, args, _comments = message

		if not args or not args[0]:
			continue

		source_text = args[0] if isinstance(args, tuple) else args
		context = args[1] if len(args) == 2 else None

		messages.append((lineno, source_text, context))

	return messages


def extract_messages_from_javascript_code(code: str) -> list[tuple[int, str, str | None]]:
	"""Extracts translatable strings from JavaScript code using babel."""

	messages = []
	from frappe.gettext.extractors.javascript import extract_javascript

	for message in extract_javascript(code):
		lineno, _func, args = message

		if not args or not args[0]:
			continue

		source_text = args[0] if isinstance(args, tuple) else args
		context = None

		if isinstance(args, tuple) and len(args) == 3 and isinstance(args[2], str):
			context = args[2]

		messages.append((lineno, source_text, context))

	return messages


def read_csv_file(path):
	"""Read CSV file and return as list of list

	:param path: File path"""

	with open(path, encoding="utf-8", newline="") as msgfile:
		data = reader(msgfile)
		newdata = [[val for val in row] for row in data]

	return newdata


def write_csv_file(path, app_messages, lang_dict):
	"""Write translation CSV file.

	:param path: File path, usually `[app]/translations`.
	:param app_messages: Translatable strings for this app.
	:param lang_dict: Full translated dict.
	"""
	app_messages.sort(key=lambda x: x[1])

	with open(path, "w", newline="") as msgfile:
		w = writer(msgfile, lineterminator="\n")

		for app_message in app_messages:
			context = None
			if len(app_message) == 2:
				path, message = app_message
			elif len(app_message) == 3:
				path, message, lineno = app_message
			elif len(app_message) == 4:
				path, message, context, lineno = app_message
			else:
				continue

			t = lang_dict.get(message, "")
			# strip whitespaces
			translated_string = CSV_STRIP_WHITESPACE_PATTERN.sub(r"{\g<1>}", t)
			if translated_string:
				w.writerow([message, translated_string, context])


def get_untranslated(lang, untranslated_file, get_all=False, app="_ALL_APPS"):
	"""Return all untranslated strings for a language and write in a file.

	:param lang: Language code.
	:param untranslated_file: Output file path.
	:param get_all: Return all strings, translated or not."""
	clear_cache()
	apps = frappe.get_all_apps(True)
	if app != "_ALL_APPS":
		if app not in apps:
			print(f"Application {app} not found!")
			return
		apps = [app]

	messages = []
	untranslated = []
	for app_name in apps:
		messages.extend(get_messages_for_app(app_name))

	messages = deduplicate_messages(messages)

	def escape_newlines(s):
		return s.replace("\\\n", "|||||").replace("\\n", "||||").replace("\n", "|||")

	if get_all:
		print(str(len(messages)) + " messages")
		with open(untranslated_file, "wb") as f:
			for m in messages:
				# replace \n with ||| so that internal linebreaks don't get split
				f.write((escape_newlines(m[1]) + os.linesep).encode("utf-8"))
	else:
		full_dict = get_all_translations(lang)

		for m in messages:
			if not full_dict.get(m[1]):
				untranslated.append(m[1])

		if untranslated:
			print(str(len(untranslated)) + " missing translations of " + str(len(messages)))
			with open(untranslated_file, "wb") as f:
				for m in untranslated:
					# replace \n with ||| so that internal linebreaks don't get split
					f.write((escape_newlines(m) + os.linesep).encode("utf-8"))
		else:
			print("all translated!")


def update_translations(lang, untranslated_file, translated_file, app="_ALL_APPS"):
	"""Update translations from a source and target file for a given language.

	:param lang: Language code (e.g. `en`).
	:param untranslated_file: File path with the messages in English.
	:param translated_file: File path with messages in language to be updated."""
	clear_cache()
	full_dict = get_all_translations(lang)

	def restore_newlines(s):
		return (
			s.replace("|||||", "\\\n")
			.replace("| | | | |", "\\\n")
			.replace("||||", "\\n")
			.replace("| | | |", "\\n")
			.replace("|||", "\n")
			.replace("| | |", "\n")
		)

	translation_dict = {}
	for key, value in zip(
		frappe.get_file_items(untranslated_file, ignore_empty_lines=False),
		frappe.get_file_items(translated_file, ignore_empty_lines=False),
		strict=False,
	):
		# undo hack in get_untranslated
		translation_dict[restore_newlines(key)] = restore_newlines(value)

	full_dict.update(translation_dict)
	apps = frappe.get_all_apps(True)

	if app != "_ALL_APPS":
		if app not in apps:
			print(f"Application {app} not found!")
			return
		apps = [app]

	for app_name in apps:
		write_translations_file(app_name, lang, full_dict)


def import_translations(lang, path):
	"""Import translations from file in standard format"""
	clear_cache()
	full_dict = get_all_translations(lang)
	full_dict.update(get_translation_dict_from_file(path, lang, "import"))

	for app in frappe.get_all_apps(True):
		write_translations_file(app, lang, full_dict)


def migrate_translations(source_app, target_app):
	"""Migrate target-app-specific translations from source-app to target-app"""
	strings_in_source_app = [m[1] for m in frappe.translate.get_messages_for_app(source_app)]
	strings_in_target_app = [m[1] for m in frappe.translate.get_messages_for_app(target_app)]
	strings_in_target_app_but_not_in_source_app = list(
		set(strings_in_target_app) - set(strings_in_source_app)
	)

	languages = frappe.translate.get_all_languages()

	source_app_translations_dir = frappe.get_app_path(source_app, "translations")
	target_app_translations_dir = frappe.get_app_path(target_app, "translations")

	if not os.path.exists(target_app_translations_dir):
		os.makedirs(target_app_translations_dir)

	for lang in languages:
		source_csv = os.path.join(source_app_translations_dir, lang + ".csv")

		if not os.path.exists(source_csv):
			continue

		target_csv = os.path.join(target_app_translations_dir, lang + ".csv")
		temp_csv = os.path.join(source_app_translations_dir, "_temp.csv")

		with open(source_csv) as s, open(target_csv, "a+") as t, open(temp_csv, "a+") as temp:
			source_reader = reader(s, lineterminator="\n")
			target_writer = writer(t, lineterminator="\n")
			temp_writer = writer(temp, lineterminator="\n")

			for row in source_reader:
				if row[0] in strings_in_target_app_but_not_in_source_app:
					target_writer.writerow(row)
				else:
					temp_writer.writerow(row)

		if not os.path.getsize(target_csv):
			os.remove(target_csv)
		os.remove(source_csv)
		os.rename(temp_csv, source_csv)


def rebuild_all_translation_files():
	"""Rebuild all translation files: `[app]/translations/[lang].csv`."""
	for lang in get_all_languages():
		for app in frappe.get_all_apps():
			write_translations_file(app, lang)


def write_translations_file(app, lang, full_dict=None, app_messages=None):
	"""Write a translation file for a given language.

	:param app: `app` for which translations are to be written.
	:param lang: Language code.
	:param full_dict: Full translated language dict (optional).
	:param app_messages: Source strings (optional).
	"""
	if not app_messages:
		app_messages = get_messages_for_app(app)

	if not app_messages:
		return

	tpath = frappe.get_app_path(app, "translations")
	frappe.create_folder(tpath)
	write_csv_file(os.path.join(tpath, lang + ".csv"), app_messages, full_dict or get_all_translations(lang))


def send_translations(translation_dict):
	"""Append translated dict in `frappe.local.response`"""
	if "__messages" not in frappe.local.response:
		frappe.local.response["__messages"] = {}

	frappe.local.response["__messages"].update(translation_dict)


def deduplicate_messages(messages):
	op = operator.itemgetter(1)
	messages = sorted(messages, key=op)
	return [next(g) for k, g in itertools.groupby(messages, op)]


@frappe.whitelist()
def update_translations_for_source(source=None, translation_dict=None):
	if not (source and translation_dict):
		return

	translation_dict = json.loads(translation_dict)

	if is_html(source):
		source = strip_html_tags(source)

	# for existing records
	translation_records = frappe.db.get_values(
		"Translation", {"source_text": source}, ["name", "language"], as_dict=1
	)
	for d in translation_records:
		if translation_dict.get(d.language, None):
			doc = frappe.get_doc("Translation", d.name)
			doc.translated_text = translation_dict.get(d.language)
			doc.save()
			# done with this lang value
			translation_dict.pop(d.language)
		else:
			frappe.delete_doc("Translation", d.name)

	# remaining values are to be inserted
	for lang, translated_text in translation_dict.items():
		doc = frappe.new_doc("Translation")
		doc.language = lang
		doc.source_text = source
		doc.translated_text = translated_text
		doc.save()

	return translation_records


@frappe.whitelist(allow_guest=True)
def get_all_languages(with_language_name: bool = False) -> list:
	"""Return all enabled language codes ar, ch etc."""

	def get_all_language_with_name():
		return frappe.get_all("Language", ["language_code", "language_name"], {"enabled": 1})

	if with_language_name:
		return frappe.cache.get_value("languages_with_name", get_all_language_with_name)
	else:
		languages = frappe.client_cache.get_value("languages")
		if not languages:
			languages = frappe.get_all("Language", filters={"enabled": 1}, pluck="name")
			frappe.client_cache.set_value("languages", languages)
		return languages


def get_preferred_language_cookie():
	return frappe.request.cookies.get("preferred_language")


def get_translated_doctypes():
	dts = frappe.get_all("DocType", {"translated_doctype": 1}, pluck="name")
	custom_dts = frappe.get_all(
		"Property Setter", {"property": "translated_doctype", "value": "1"}, pluck="doc_type"
	)
	return unique(dts + custom_dts)


@contextmanager
def print_language(language: str):
	"""Ensure correct globals for printing in a specific language.

	Usage:

	```
	with print_language("de"):
	    html = frappe.get_print(...)
	```
	"""
	if not language or language == frappe.local.lang:
		# do nothing
		yield
		return

	# remember original values
	_lang = frappe.local.lang
	_jenv = frappe.local.jenv

	# set language, empty any existing lang_full_dict and jenv
	frappe.local.lang = language
	frappe.local.jenv = None

	yield

	# restore original values
	frappe.local.lang = _lang
	frappe.local.jenv = _jenv


# Backward compatibility
get_full_dict = get_all_translations
load_lang = get_translations_from_apps
