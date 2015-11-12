# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

"""
	frappe.translate
	~~~~~~~~~~~~~~~~

	Translation tools for frappe
"""

import frappe, os, re, codecs, json
from frappe.utils.jinja import render_include
from jinja2 import TemplateError
import itertools, operator

def guess_language(lang_list=None):
	"""Set `frappe.local.lang` from HTTP headers at beginning of request"""
	lang_codes = frappe.request.accept_languages.values()
	if not lang_codes:
		return frappe.local.lang

	guess = None
	if not lang_list:
		lang_list = get_all_languages() or []

	for l in lang_codes:
		code = l.strip()
		if code in lang_list or code == "en":
			guess = code
			break

		# check if parent language (pt) is setup, if variant (pt-BR)
		if "-" in code:
			code = code.split("-")[0]
			if code in lang_list:
				guess = code
				break

	return guess or frappe.local.lang

def get_user_lang(user=None):
	"""Set frappe.local.lang from user preferences on session beginning or resumption"""
	if not user:
		user = frappe.session.user

	# via cache
	lang = frappe.cache().hget("lang", user)

	if not lang:

		# if defined in user profile
		user_lang = frappe.db.get_value("User", user, "language")
		if user_lang and user_lang!="Loading...":
			lang = get_lang_dict().get(user_lang) or frappe.local.lang
		else:
			default_lang = frappe.db.get_default("lang")
			lang = default_lang or frappe.local.lang

		frappe.cache().hset("lang", user, lang or "en")

	return lang

def set_default_language(language):
	"""Set Global default language"""
	lang = get_lang_dict()[language]
	frappe.db.set_default("lang", lang)
	frappe.local.lang = lang

def get_all_languages():
	"""Returns all language codes ar, ch etc"""
	return [a.split()[0] for a in get_lang_info()]

def get_lang_dict():
	"""Returns all languages in dict format, full name is the key e.g. `{"english":"en"}`"""
	return dict([[a[1], a[0]] for a in [a.split(None, 1) for a in get_lang_info()]])

def get_language_from_code(lang):
	return dict(a.split(None, 1) for a in get_lang_info()).get(lang)

def get_lang_info():
	"""Returns a listified version of `apps/languages.txt`"""
	return frappe.cache().get_value("langinfo",
		lambda:frappe.get_file_items(os.path.join(frappe.local.sites_path, "languages.txt")))

def get_dict(fortype, name=None):
	"""Returns translation dict for a type of object.

	 :param fortype: must be one of `doctype`, `page`, `report`, `include`, `jsfile`, `boot`
	 :param name: name of the document for which assets are to be returned.
	 """
	fortype = fortype.lower()
	cache = frappe.cache()
	asset_key = fortype + ":" + (name or "-")
	translation_assets = cache.hget("translation_assets", frappe.local.lang) or {}

	if not asset_key in translation_assets:
		if fortype=="doctype":
			messages = get_messages_from_doctype(name)
		elif fortype=="page":
			messages = get_messages_from_page(name)
		elif fortype=="report":
			messages = get_messages_from_report(name)
		elif fortype=="include":
			messages = get_messages_from_include_files()
		elif fortype=="jsfile":
			messages = get_messages_from_file(name)
		elif fortype=="boot":
			messages = get_messages_from_include_files()
			messages += frappe.db.sql("select 'DocType:', name from tabDocType")
			messages += frappe.db.sql("select 'Role:', name from tabRole")
			messages += frappe.db.sql("select 'Module:', name from `tabModule Def`")

		translation_assets[asset_key] = make_dict_from_messages(messages)
		translation_assets[asset_key].update(get_dict_from_hooks(fortype, name))

		cache.hset("translation_assets", frappe.local.lang, translation_assets)

	return translation_assets[asset_key]

def get_dict_from_hooks(fortype, name):
	translated_dict = {}

	hooks = frappe.get_hooks("get_translated_dict")
	for (hook_fortype, fortype_name) in hooks:
		if hook_fortype == fortype and fortype_name == name:
			for method in hooks[(hook_fortype, fortype_name)]:
				translated_dict.update(frappe.get_attr(method)())

	return translated_dict

def add_lang_dict(code):
	"""Extracts messages and returns Javascript code snippet to be appened at the end
	of the given script

	:param code: Javascript code snippet to which translations needs to be appended."""
	messages = extract_messages_from_code(code)
	messages = [message for pos, message in messages]
	code += "\n\n$.extend(frappe._messages, %s)" % json.dumps(make_dict_from_messages(messages))
	return code

def make_dict_from_messages(messages, full_dict=None):
	"""Returns translated messages as a dict in Language specified in `frappe.local.lang`

	:param messages: List of untranslated messages
	"""
	out = {}
	if full_dict==None:
		full_dict = get_full_dict(frappe.local.lang)

	for m in messages:
		if m[1] in full_dict:
			out[m[1]] = full_dict[m[1]]
	return out

def get_lang_js(fortype, name):
	"""Returns code snippet to be appended at the end of a JS script.

	:param fortype: Type of object, e.g. `DocType`
	:param name: Document name
	"""
	return "\n\n$.extend(frappe._messages, %s)" % json.dumps(get_dict(fortype, name))

def get_full_dict(lang):
	"""Load and return the entire translations dictionary for a language from :meth:`frape.cache`

	:param lang: Language Code, e.g. `hi`
	"""
	if not lang or lang == "en":
		return {}

	if not frappe.local.lang_full_dict:
		frappe.local.lang_full_dict = frappe.cache().hget("lang_full_dict", lang)
		if not frappe.local.lang_full_dict:
			frappe.local.lang_full_dict = load_lang(lang)

			# cache lang
			frappe.cache().hset("lang_full_dict", lang, frappe.local.lang_full_dict)

	return frappe.local.lang_full_dict

def load_lang(lang, apps=None):
	"""Combine all translations from `.csv` files in all `apps`"""
	out = {}
	for app in (apps or frappe.get_all_apps(True)):
		path = os.path.join(frappe.get_pymodule_path(app), "translations", lang + ".csv")
		if os.path.exists(path):
			csv_content = read_csv_file(path)

			cleaned = {}
			for item in csv_content:
				if len(item)==3:
					# with file and line numbers
					cleaned[item[1]] = item[2]

				elif len(item)==2:
					cleaned[item[0]] = item[1]

				else:
					raise Exception("Bad translation in '{app}' for language '{lang}': {values}".format(
						app=app, lang=lang, values=repr(item).encode("utf-8")
					))

			out.update(cleaned)
	return out

def clear_cache():
	"""Clear all translation assets from :meth:`frappe.cache`"""
	cache = frappe.cache()
	cache.delete_key("langinfo")
	cache.delete_key("lang_full_dict")
	cache.delete_key("translation_assets")

def get_messages_for_app(app):
	"""Returns all messages (list) for a specified `app`"""
	messages = []
	modules = ", ".join(['"{}"'.format(m.title().replace("_", " ")) \
		for m in frappe.local.app_modules[app]])

	# doctypes
	if modules:
		for name in frappe.db.sql_list("""select name from tabDocType
			where module in ({})""".format(modules)):
			messages.extend(get_messages_from_doctype(name))

		# pages
		for name, title in frappe.db.sql("""select name, title from tabPage
			where module in ({})""".format(modules)):
			messages.append((None, title or name))
			messages.extend(get_messages_from_page(name))


		# reports
		for name in frappe.db.sql_list("""select tabReport.name from tabDocType, tabReport
			where tabReport.ref_doctype = tabDocType.name
				and tabDocType.module in ({})""".format(modules)):
			messages.append((None, name))
			messages.extend(get_messages_from_report(name))
			for i in messages:
				if not isinstance(i, tuple):
					raise Exception

	# app_include_files
	messages.extend(get_all_messages_from_js_files(app))

	# server_messages
	messages.extend(get_server_messages(app))
	return deduplicate_messages(messages)

def get_messages_from_doctype(name):
	"""Extract all translatable messages for a doctype. Includes labels, Python code,
	Javascript code, html templates"""
	messages = []
	meta = frappe.get_meta(name)

	messages = [meta.name, meta.module]

	if meta.description:
		messages.append(meta.description)

	# translations of field labels, description and options
	for d in meta.get("fields"):
		messages.extend([d.label, d.description])

		if d.fieldtype=='Select' and d.options:
			options = d.options.split('\n')
			if not "icon" in options[0]:
				messages.extend(options)

	# translations of roles
	for d in meta.get("permissions"):
		if d.role:
			messages.append(d.role)

	messages = [message for message in messages if message]
	messages = [('DocType: ' + name, message) for message in messages if is_translatable(message)]

	# extract from js, py files
	doctype_file_path = frappe.get_module_path(meta.module, "doctype", meta.name, meta.name)
	messages.extend(get_messages_from_file(doctype_file_path + ".js"))
	messages.extend(get_messages_from_file(doctype_file_path + "_list.js"))
	messages.extend(get_messages_from_file(doctype_file_path + "_list.html"))
	messages.extend(get_messages_from_file(doctype_file_path + "_calendar.js"))
	return messages

def get_messages_from_page(name):
	"""Returns all translatable strings from a :class:`frappe.core.doctype.Page`"""
	return _get_messages_from_page_or_report("Page", name)


def get_messages_from_report(name):
	"""Returns all translatable strings from a :class:`frappe.core.doctype.Report`"""
	report = frappe.get_doc("Report", name)
	messages = _get_messages_from_page_or_report("Report", name,
		frappe.db.get_value("DocType", report.ref_doctype, "module"))
	# TODO position here!
	if report.query:
		messages.extend([(None, message) for message in re.findall('"([^:,^"]*):', report.query) if is_translatable(message)])
	messages.append((None,report.report_name))
	return messages

def _get_messages_from_page_or_report(doctype, name, module=None):
	if not module:
		module = frappe.db.get_value(doctype, name, "module")

	doc_path = frappe.get_module_path(module, doctype, name)

	messages = get_messages_from_file(os.path.join(doc_path, frappe.scrub(name) +".py"))

	if os.path.exists(doc_path):
		for filename in os.listdir(doc_path):
			if filename.endswith(".js") or filename.endswith(".html"):
				messages += get_messages_from_file(os.path.join(doc_path, filename))

	return messages

def get_server_messages(app):
	"""Extracts all translatable strings (tagged with :func:`frappe._`) from Python modules inside an app"""
	messages = []
	for basepath, folders, files in os.walk(frappe.get_pymodule_path(app)):
		for dontwalk in (".git", "public", "locale"):
			if dontwalk in folders: folders.remove(dontwalk)

		for f in files:
			if f.endswith(".py") or f.endswith(".html") or f.endswith(".js"):
				messages.extend(get_messages_from_file(os.path.join(basepath, f)))

	return messages

def get_messages_from_include_files(app_name=None):
	"""Returns messages from js files included at time of boot like desk.min.js for desk and web"""
	messages = []
	for file in (frappe.get_hooks("app_include_js", app_name=app_name) or []) + (frappe.get_hooks("web_include_js", app_name=app_name) or []):
		messages.extend(get_messages_from_file(os.path.join(frappe.local.sites_path, file)))

	return messages

def get_all_messages_from_js_files(app_name=None):
	"""Extracts all translatable strings from app `.js` files"""
	messages = []
	for app in ([app_name] if app_name else frappe.get_installed_apps()):
		if os.path.exists(frappe.get_app_path(app, "public")):
			for basepath, folders, files in os.walk(frappe.get_app_path(app, "public")):
				if "frappe/public/js/lib" in basepath:
					continue

				for fname in files:
					if fname.endswith(".js") or fname.endswith(".html"):
						messages.extend(get_messages_from_file(os.path.join(basepath, fname)))

	return messages

def get_messages_from_file(path):
	"""Returns a list of transatable strings from a code file

	:param path: path of the code file
	"""
	apps_path = get_bench_dir()
	if os.path.exists(path):
		with open(path, 'r') as sourcefile:
			return [(os.path.relpath(" +".join([path, str(pos)]), apps_path),
					message) for pos, message in  extract_messages_from_code(sourcefile.read(), path.endswith(".py"))]
	else:
		print "Translate: {0} missing".format(os.path.abspath(path))
		return []

def extract_messages_from_code(code, is_py=False):
	"""Extracts translatable srings from a code file

	:param code: code from which translatable files are to be extracted
	:param is_py: include messages in triple quotes e.g. `_('''message''')`"""
	try:
		code = render_include(code)
	except TemplateError:
		# Exception will occur when it encounters John Resig's microtemplating code
		pass

	messages = []
	messages += [(m.start(), m.groups()[0]) for m in re.compile('_\("([^"]*)"').finditer(code)]
	messages += [(m.start(), m.groups()[0]) for m in re.compile("_\('([^']*)'").finditer(code)]
	if is_py:
		messages += [(m.start(), m.groups()[0]) for m in re.compile('_\("{3}([^"]*)"{3}.*\)').finditer(code)]

	messages = [(pos, message) for pos, message in messages if is_translatable(message)]
	return pos_to_line_no(messages, code)

def is_translatable(m):
	if re.search("[a-z]", m) and not m.startswith("icon-") and not m.endswith("px") and not m.startswith("eval:"):
		return True
	return False

def pos_to_line_no(messages, code):
	ret = []
	messages = sorted(messages, key=lambda x: x[0])
	newlines = [m.start() for m in re.compile('\\n').finditer(code)]
	line = 1
	newline_i = 0
	for pos, message in messages:
		while newline_i < len(newlines) and pos > newlines[newline_i]:
			line+=1
			newline_i+= 1
		ret.append((line, message))
	return ret

def read_csv_file(path):
	"""Read CSV file and return as list of list

	:param path: File path"""
	from csv import reader
	with codecs.open(path, 'r', 'utf-8') as msgfile:
		data = msgfile.read()

		# for japanese! #wtf
		data = data.replace(chr(28), "").replace(chr(29), "")
		data = reader([r.encode('utf-8') for r in data.splitlines()])
		newdata = [[unicode(val, 'utf-8') for val in row] for row in data]
	return newdata

def write_csv_file(path, app_messages, lang_dict):
	"""Write translation CSV file.

	:param path: File path, usually `[app]/translations`.
	:param app_messages: Translatable strings for this app.
	:param lang_dict: Full translated dict.
	"""
	app_messages.sort()
	from csv import writer
	with open(path, 'wb') as msgfile:
		w = writer(msgfile, lineterminator='\n')
		for p, m in app_messages:
			t = lang_dict.get(m, '')
			# strip whitespaces
			t = re.sub('{\s?([0-9]+)\s?}', "{\g<1>}", t)
			w.writerow([p.encode('utf-8') if p else '', m.encode('utf-8'), t.encode('utf-8')])

def get_untranslated(lang, untranslated_file, get_all=False):
	"""Returns all untranslated strings for a language and writes in a file

	:param lang: Language code.
	:param untranslated_file: Output file path.
	:param get_all: Return all strings, translated or not."""
	clear_cache()
	apps = frappe.get_all_apps(True)

	messages = []
	untranslated = []
	for app in apps:
		messages.extend(get_messages_for_app(app))

	messages = deduplicate_messages(messages)

	def escape_newlines(s):
		return (s.replace("\\\n", "|||||")
				.replace("\\n", "||||")
				.replace("\n", "|||"))

	if get_all:
		print str(len(messages)) + " messages"
		with open(untranslated_file, "w") as f:
			for m in messages:
				# replace \n with ||| so that internal linebreaks don't get split
				f.write((escape_newlines(m[1]) + os.linesep).encode("utf-8"))
	else:
		full_dict = get_full_dict(lang)

		for m in messages:
			if not full_dict.get(m[1]):
				untranslated.append(m[1])

		if untranslated:
			print str(len(untranslated)) + " missing translations of " + str(len(messages))
			with open(untranslated_file, "w") as f:
				for m in untranslated:
					# replace \n with ||| so that internal linebreaks don't get split
					f.write((escape_newlines(m) + os.linesep).encode("utf-8"))
		else:
			print "all translated!"

def update_translations(lang, untranslated_file, translated_file):
	"""Update translations from a source and target file for a given language.

	:param lang: Language code (e.g. `en`).
	:param untranslated_file: File path with the messages in English.
	:param translated_file: File path with messages in language to be updated."""
	clear_cache()
	full_dict = get_full_dict(lang)

	def restore_newlines(s):
		return (s.replace("|||||", "\\\n")
				.replace("| | | | |", "\\\n")
				.replace("||||", "\\n")
				.replace("| | | |", "\\n")
				.replace("|||", "\n")
				.replace("| | |", "\n"))

	translation_dict = {}
	for key, value in zip(frappe.get_file_items(untranslated_file, ignore_empty_lines=False),
		frappe.get_file_items(translated_file, ignore_empty_lines=False)):

		# undo hack in get_untranslated
		translation_dict[restore_newlines(key)] = restore_newlines(value)

	full_dict.update(translation_dict)

	for app in frappe.get_all_apps(True):
		write_translations_file(app, lang, full_dict)

def rebuild_all_translation_files():
	"""Rebuild all translation files: `[app]/translations/[lang].csv`."""
	for lang in get_all_languages():
		for app in frappe.get_all_apps():
			write_translations_file(app, lang)

def write_translations_file(app, lang, full_dict=None, app_messages=None):
	"""Write a translation file for a given language.

	:param app: `app` for which translations are to be written.
	:param lang: Language code.
	:param full_dict: Full translated langauge dict (optional).
	:param app_messages: Source strings (optional).
	"""
	if not app_messages:
		app_messages = get_messages_for_app(app)

	if not app_messages:
		return

	tpath = frappe.get_pymodule_path(app, "translations")
	frappe.create_folder(tpath)
	write_csv_file(os.path.join(tpath, lang + ".csv"),
		app_messages, full_dict or get_full_dict(lang))

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
		ret.append(g.next())
	return ret

def get_bench_dir():
	return os.path.join(frappe.__file__, '..', '..', '..', '..')

def rename_language(old_name, new_name):
	language_in_system_settings = frappe.db.get_single_value("System Settings", "language")
	if language_in_system_settings == old_name:
		frappe.db.set_value("System Settings", "System Settings", "language", new_name)

	frappe.db.sql("""update `tabUser` set language=%(new_name)s where language=%(old_name)s""",
		{ "old_name": old_name, "new_name": new_name })
