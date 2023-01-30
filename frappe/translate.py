# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
	frappe.translate
	~~~~~~~~~~~~~~~~

	Translation tools for frappe
"""

import csv
import functools
import gettext
import glob
import itertools
import json
import operator
import os
import re
from contextlib import contextmanager
from datetime import datetime

from babel.messages.catalog import Catalog
from babel.messages.extract import extract_from_dir, extract_python
from babel.messages.mofile import read_mo, write_mo
from babel.messages.pofile import read_po, write_po

import frappe
from frappe.utils import is_html, strip_html_tags, unique

TRANSLATE_PATTERN = re.compile(
	r"_\(\s*"  # starts with literal `_(`, ignore following whitespace/newlines
	# BEGIN: message search
	r"([\"']{,3})"  # start of message string identifier - allows: ', ", """, '''; 1st capture group
	r"(?P<message>((?!\1).)*)"  # Keep matching until string closing identifier is met which is same as 1st capture group
	r"\1"  # match exact string closing identifier
	# END: message search
	# BEGIN: python context search
	r"(\s*,\s*context\s*=\s*"  # capture `context=` with ignoring whitespace
	r"([\"'])"  # start of context string identifier; 5th capture group
	r"(?P<py_context>((?!\5).)*)"  # capture context string till closing id is found
	r"\5"  # match context string closure
	r")?"  # match 0 or 1 context strings
	# END: python context search
	# BEGIN: JS context search
	r"(\s*,\s*(.)*?\s*(,\s*"  # skip message format replacements: ["format", ...] | null | []
	r"([\"'])"  # start of context string; 11th capture group
	r"(?P<js_context>((?!\11).)*)"  # capture context string till closing id is found
	r"\11"  # match context string closure
	r")*"
	r")*"  # match one or more context string
	# END: JS context search
	r"\s*\)"  # Closing function call ignore leading whitespace/newlines
)
REPORT_TRANSLATE_PATTERN = re.compile('"([^:,^"]*):')
CSV_STRIP_WHITESPACE_PATTERN = re.compile(r"{\s?([0-9]+)\s?}")

APP_TRANSLATION_KEY = "translations_from_apps"
DEFAULT_LANG = "en"
LOCALE_DIR = "locale"
MERGED_TRANSLATION_KEY = "merged_translations"
POT_FILE = "main.pot"
TRANSLATION_DOMAIN = "messages"
USER_TRANSLATION_KEY = "lang_user_translations"


def get_language(lang_list: list = None) -> str:
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
		language = get_lang_code(
			frappe.form_dict._lang or get_parent_language(frappe.form_dict._lang)
		)
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

		parent_language = get_parent_language(language)
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
	return frappe.db.get_default("lang") or "en"


@functools.lru_cache
def get_parent_language(lang: str) -> str:
	"""If the passed language is a variant, return its parent

	Eg:
	        1. zh-TW -> zh
	        2. sr-BA -> sr
	"""
	is_language_variant = "-" in lang
	if is_language_variant:
		return lang[: lang.index("-")]


def get_user_lang(user: str = None) -> str:
	"""Set frappe.local.lang from user preferences on session beginning or resumption"""
	user = user or frappe.session.user
	lang = frappe.cache().hget("lang", user)

	if not lang:
		# User.language => Session Defaults => frappe.local.lang => 'en'
		lang = (
			frappe.db.get_value("User", user, "language")
			or frappe.db.get_default("lang")
			or frappe.local.lang
			or "en"
		)

		frappe.cache().hset("lang", user, lang)

	return lang


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
	"""Returns all languages in dict format, full name is the key e.g. `{"english":"en"}`"""
	return dict(
		frappe.get_all(
			"Language", fields=["language_name", "name"], order_by="modified", as_list=True
		)
	)


def get_translator(lang: str, localedir: str | None = LOCALE_DIR, context: bool | None = False):
	t = gettext.translation(
		TRANSLATION_DOMAIN, localedir=localedir, languages=(lang,), fallback=True
	)

	if context:
		return t.pgettext

	return t.gettext


def generate_pot(target_app: str | None = None):
	"""
	Generate a POT (PO template) file. This file will contain only messages IDs.
	https://en.wikipedia.org/wiki/Gettext

	:param target_app: If specified, limit to `app`
	"""
	apps = [target_app] if target_app else frappe.get_all_apps(True)
	method_map = [
		("**.py", "frappe.translate.babel_extract_python"),
		("**/doctype/*/*.json", "frappe.translate.babel_extract_doctype_json"),
	]

	for app in apps:
		app_path = frappe.get_pymodule_path(app)
		loc_path = os.path.join(app_path, "locale")
		pot_path = os.path.join(loc_path, "main.pot")
		os.makedirs(loc_path, exist_ok=True)

		c = Catalog(
			domain="messages",
			msgid_bugs_address="contact@frappe.io",
			language_team="contact@frappe.io",
			copyright_holder="Frappe Technologies Pvt. Ltd.",
			last_translator="contact@frappe.io",
			project="Frappe Translation",
			creation_date=datetime.now(),
			revision_date=datetime.now(),
			fuzzy=False,
		)

		for i in extract_from_dir(app_path, method_map):
			_file, _lineno, msgid, *rest = i

			if not msgid:
				continue

			messages = msgid if isinstance(msgid, tuple) else [msgid]

			for m in messages:
				c.add(m)

			c.add(msgid)

		with open(pot_path, "wb") as f:
			write_po(f, c)
			print(f"POT file created at {pot_path}")


def new_po(lang_code, target_app: str | None = None):
	apps = [target_app] if target_app else frappe.get_all_apps(True)

	for target_app in apps:
		app_path = frappe.get_app_path(target_app)
		loc_path = os.path.join(app_path, "locale")
		pot_path = os.path.join(loc_path, POT_FILE)
		po_path = os.path.join(loc_path, lang_code, "LC_MESSAGES", "messages.po")

		if os.path.exists(po_path):
			print(f"{po_path} exists. Skipping")
			continue

		pot_file = open(pot_path)
		pot_catalog = read_po(pot_file)
		pot_file.close()

		po_catalog = Catalog(
			domain="messages",
			msgid_bugs_address="contact@frappe.io",
			language_team="contact@frappe.io",
			copyright_holder="Frappe Technologies Pvt. Ltd.",
			last_translator="contact@frappe.io",
			project="Frappe Translation",
			creation_date=datetime.now(),
			revision_date=datetime.now(),
			fuzzy=False,
		)

		for m in pot_catalog:
			po_catalog.add(m.id, context=m.context)

		with open(po_path, "wb") as po_file:
			write_po(po_file, po_catalog)
			print(f"PO file created_at {po_path}")
			print(
				"You will need to add the language in frappe/geo/languages.json, if you haven't done it already."
			)


def compile(target_app: str | None = None):
	apps = [target_app] if target_app else frappe.get_all_apps(True)

	for app in apps:
		app_path = frappe.get_app_path(app)
		loc_path = os.path.join(app_path, "locale")
		po_files = glob.glob("**/*.po", root_dir=loc_path, recursive=True)

		for file in po_files:
			po_path = os.path.join(loc_path, file)
			po_dir, _ = os.path.split(po_path)
			mo_path = os.path.join(po_dir, "messages.mo")

			with open(po_path) as po_file:
				c = read_po(po_file)
				with open(mo_path, "wb") as mo_file:
					write_mo(mo_file, c)
					print(f"MO file created at {mo_path}")


def update_po(target_app: str | None = None):
	"""
	Add keys to available PO files, from POT file. This could be used to keep
	track of available keys, and missing translations

	:param target_app: Limit operation to `app`, if specified
	"""
	apps = [target_app] if target_app else frappe.get_all_apps(True)

	for app in apps:
		app_path = frappe.get_app_path(app)
		loc_path = os.path.join(app_path, LOCALE_DIR)
		pot_path = os.path.join(loc_path, POT_FILE)
		po_files = glob.glob("**/*.po", root_dir=loc_path, recursive=True)

		pot_file = open(pot_path)
		pot_catalog = read_po(pot_file)
		pot_file.close()

		for f in po_files:
			po_path = os.path.join(loc_path, f)

			with open(po_path, "r+b") as po_file:
				po_catalog = read_po(po_file)

				for i in pot_catalog:
					if not po_catalog.get(i.id, context=i.context):
						po_catalog.add(i.id, context=i.context)

				write_po(po_file, po_catalog)
				print(f"PO file modified at {po_path}")


def f(msg: str, context: str = None, lang: str = DEFAULT_LANG) -> str:
	"""
	Method to translate a string

	:param msg: Key to translate
	:param context: Translation context
	:param lang: Language to fetch
	:return: Translated string. Could be original string
	"""
	from frappe import as_unicode
	from frappe.utils import is_html, strip_html_tags

	if not lang:
		lang = DEFAULT_LANG

	msg = as_unicode(msg).strip()

	if is_html(msg):
		msg = strip_html_tags(msg)

	apps = frappe.get_all_apps()

	for app in apps:
		app_path = frappe.get_pymodule_path(app)
		locale_path = os.path.join(app_path, LOCALE_DIR)
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


def get_messages_for_boot():
	"""
	Return all message translations that are required on boot
	"""
	messages = get_all_translations(frappe.local.lang)
	messages.update(get_dict_from_hooks("boot", None))

	return messages


def get_dict_from_hooks(fortype: str, name: str) -> dict[str, str]:
	"""
	Get and run a custom translator method from hooks for item.

	Hook example:
	```
	get_translated_dict = {
		("doctype", "Global Defaults"): "frappe.geo.country_info.get_translated_dict",
	}
	```

	:param fortype: Item type. eg: doctype
	:param name: Item name. eg: User
	:return: Dictionary with translated messages
	"""
	translated_dict = {}
	hooks = frappe.get_hooks("get_translated_dict")

	for (hook_fortype, fortype_name) in hooks:
		if hook_fortype == fortype and fortype_name == name:
			for method in hooks[(hook_fortype, fortype_name)]:
				translated_dict.update(frappe.get_attr(method)())

	return translated_dict


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

		try:
			# get user specific translation data
			user_translations = get_user_translations(lang)
			all_translations.update(user_translations)
		except:
			pass

		return all_translations

	try:
		return frappe.cache().hget(MERGED_TRANSLATION_KEY, lang, generator=t)
	except:
		# People mistakenly call translation function on global variables where
		# locals are not initialized, translations don't make much sense there
		return {}


def get_translations_from_apps(lang, apps=None):
	"""
	Combine all translations from `.mo` files in all `apps`. For derivative
	languages (es-GT), take translations from the base language (es) and then
	update translations from the child (es-GT)
	"""
	if not lang or lang == DEFAULT_LANG:
		return {}

	def t():
		translations = {}

		for app in apps or frappe.get_all_apps(True):
			app_path = frappe.get_pymodule_path(app)
			localedir = os.path.join(app_path, LOCALE_DIR)
			mo_files = gettext.find(TRANSLATION_DOMAIN, localedir, (lang,), True)

			for file in mo_files:
				with open(file, "rb") as f:
					po = read_mo(f)
					for m in po:
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
				key += ":" + t.context
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


def is_translatable(m):
	if (
		re.search("[a-zA-Z]", m)
		and not m.startswith("fa fa-")
		and not m.endswith("px")
		and not m.startswith("eval:")
	):
		return True
	return False


def add_line_number(messages, code):
	ret = []
	messages = sorted(messages, key=lambda x: x[0])
	newlines = [m.start() for m in re.compile(r"\n").finditer(code)]
	line = 1
	newline_i = 0
	for pos, message, context in messages:
		while newline_i < len(newlines) and pos > newlines[newline_i]:
			line += 1
			newline_i += 1
		ret.append([line, message, context])
	return ret


def send_translations(translation_dict):
	"""Append translated dict in `frappe.local.response`"""
	if "__messages" not in frappe.local.response:
		frappe.local.response["__messages"] = {}

	frappe.local.response["__messages"].update(translation_dict)


def deduplicate_messages(messages):
	ret = []
	op = operator.itemgetter(1)
	messages = sorted(messages, key=op)
	for k, g in itertools.groupby(messages, op):
		ret.append(next(g))
	return ret


def csv_to_po(file: str, localedir: str):
	l = os.path.split(file)[-1].split(".")[0].replace("-", "_")
	m = os.path.join(localedir, l, "LC_MESSAGES")
	os.makedirs(m, exist_ok=True)
	p = os.path.join(m, "messages.po")

	c = Catalog(
		domain="messages",
		msgid_bugs_address="contact@frappe.io",
		language_team="contact@frappe.io",
		copyright_holder="Frappe Technologies Pvt. Ltd.",
		last_translator="contact@frappe.io",
		project="frappe translation",
		version="0.1",
		creation_date=datetime.now(),
		revision_date=datetime.now(),
		fuzzy=False,
	)

	with open(file) as f:
		r = csv.reader(f)

		for row in r:
			if len(row) <= 2:
				continue

			msgid = escape_percent(row[0])
			msgstr = escape_percent(row[1])
			msgctxt = row[2] if len(row) >= 3 else None

			c.add(msgid, string=msgstr, context=msgctxt)

	with open(p, "wb") as f:
		write_po(f, c, sort_output=True)
		print(f"PO file created at {p}")


def migrate(app: str | None = None):
	apps = [app] if app else frappe.get_all_apps(True)

	for app in apps:
		app_path = frappe.get_app_path(app)
		translations_path = os.path.join(app_path, "translations")

		if not os.path.exists(translations_path):
			continue

		if not os.path.isdir(translations_path):
			continue

		po_locale_dir = os.path.join(app_path, "locale")
		csv_files = [i for i in os.listdir(translations_path) if i.endswith(".csv")]

		for f in csv_files:
			csv_to_po(os.path.join(translations_path, f), po_locale_dir)


def escape_percent(s: str):
	return s.replace("%", "&#37;")


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


@frappe.whitelist()
def get_translations(source_text):
	if is_html(source_text):
		source_text = strip_html_tags(source_text)

	return frappe.db.get_list(
		"Translation",
		fields=["name", "language", "translated_text as translation"],
		filters={"source_text": source_text},
	)


@frappe.whitelist()
def get_messages(language, start=0, page_length=100, search_text=""):
	from frappe.frappeclient import FrappeClient

	translator = FrappeClient(get_translator_url())
	translated_dict = translator.post_api(
		"translator.api.get_strings_for_translation", params=locals()
	)

	return translated_dict


def babel_extract_python(*args, **kwargs):
	"""
	Wrapper around babel's `extract_python`, handling our own implementation of `_()`
	"""
	for lineno, funcname, messages, comments in extract_python(*args, **kwargs):
		if funcname == "_" and isinstance(messages, tuple) and len(messages) > 1:
			funcname = "pgettext"
			messages = (messages[-1], messages[0])  # (context, message)

		yield lineno, funcname, messages, comments


def babel_extract_doctype_json(fileobj, *args, **kwargs):
	"""
    Extract messages from DocType JSON files. To be used to babel extractor

    :param fileobj: the file-like object the messages should be extracted from
    :rtype: `iterator`
	"""
	data = json.load(fileobj)

	if isinstance(data, list):
		return

	doctype = data.get("name")

	yield None, "_", doctype, ["Name of a DocType"]

	messages = []
	fields = data.get("fields", [])
	links = data.get("links", [])

	for field in fields:
		fieldtype = field.get("fieldtype")

		if label := field.get("label"):
			messages.append((label, f"Label of a {fieldtype} field in DocType '{doctype}'"))

		if description := field.get("description"):
			messages.append(
				(description, f"Description of a {fieldtype} field in DocType '{doctype}'")
			)

		if message := field.get("options"):
			if fieldtype == "Select":
				select_options = [
					option for option in message.split("\n") if option and not option.isdigit()
				]

				if select_options and "icon" in select_options[0]:
					continue

				messages.extend(
					(option, f"Option for a {fieldtype} field in DocType '{doctype}'")
					for option in select_options
				)
			elif fieldtype == "HTML":
				messages.append(
					(message, f"Content of an {fieldtype} field in DocType '{doctype}'")
				)

	for link in links:
		if group := link.get("group"):
			messages.append((group, f"Group in {doctype}'s connections"))

		if link_doctype := link.get("link_doctype"):
			messages.append((link_doctype, f"Linked DocType in {doctype}'s connections"))

	# By using "pgettext" as the function name we can supply the doctype as context
	yield from ((None, "pgettext", (doctype, message), [comment]) for message, comment in messages)

	# Role names do not get context because they are used with multiple doctypes
	yield from (
		(None, "_", perm["role"], ["Name of a role"])
		for perm in data.get("permissions", [])
		if "role" in perm
	)


@frappe.whitelist()
def get_source_additional_info(source, language=""):
	from frappe.frappeclient import FrappeClient

	translator = FrappeClient(get_translator_url())
	return translator.post_api("translator.api.get_source_additional_info", params=locals())


@frappe.whitelist()
def get_contributions(language):
	return frappe.get_all(
		"Translation",
		fields=["*"],
		filters={
			"contributed": 1,
		},
	)


@frappe.whitelist()
def get_contribution_status(message_id):
	from frappe.frappeclient import FrappeClient

	doc = frappe.get_doc("Translation", message_id)
	translator = FrappeClient(get_translator_url())
	contributed_translation = translator.get_api(
		"translator.api.get_contribution_status",
		params={"translation_id": doc.contribution_docname},
	)
	return contributed_translation


def get_translator_url():
	return frappe.get_hooks()["translator_url"][0]


@frappe.whitelist(allow_guest=True)
def get_all_languages(with_language_name: bool = False) -> list:
	"""Returns all enabled language codes ar, ch etc"""

	def get_language_codes():
		return frappe.get_all("Language", filters={"enabled": 1}, pluck="name")

	def get_all_language_with_name():
		return frappe.get_all("Language", ["language_code", "language_name"], {"enabled": 1})

	if not frappe.db:
		frappe.connect()

	if with_language_name:
		return frappe.cache().get_value("languages_with_name", get_all_language_with_name)
	else:
		return frappe.cache().get_value("languages", get_language_codes)


@frappe.whitelist(allow_guest=True)
def set_preferred_language_cookie(preferred_language: str):
	frappe.local.cookie_manager.set_cookie("preferred_language", preferred_language)


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
	    html = frappe.get_print( ... )
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
