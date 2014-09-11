# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

"""
Contributing:
1. Add the .csv file
2. Run import
3. Then run translate
"""

# loading
# doctype, page, report
# boot(startup)
# frappe.require
# frappe._

import frappe, os, re, codecs, json
from frappe.utils.jinja import render_include
from jinja2 import TemplateError

def guess_language_from_http_header(lang):
	"""set frappe.local.lang from HTTP headers at beginning of request"""
	if not lang:
		return frappe.local.lang

	guess = None
	lang_list = get_all_languages() or []

	if ";" in lang: # not considering weightage
		lang = lang.split(";")[0]
	if "," in lang:
		lang = lang.split(",")
	else:
		lang = [lang]

	for l in lang:
		code = l.strip()
		if code in lang_list:
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
	"""set frappe.local.lang from user preferences on session beginning or resumption"""
	if not user:
		user = frappe.session.user

	# via cache
	lang = frappe.cache().get_value("lang:" + user)

	if not lang:

		# if defined in user profile
		user_lang = frappe.db.get_value("User", user, "language")
		if user_lang and user_lang!="Loading...":
			lang = get_lang_dict().get(user_lang)
		else:
			default_lang = frappe.db.get_default("lang")
			lang = default_lang or frappe.local.lang

		frappe.cache().set_value("lang:" + user, lang or "en")

	return lang

def set_default_language(language):
	lang = get_lang_dict()[language]
	frappe.db.set_default("lang", lang)
	frappe.local.lang = lang

def get_all_languages():
	return [a.split()[0] for a in get_lang_info()]

def get_lang_dict():
	return dict([[a[1], a[0]] for a in [a.split(None, 1) for a in get_lang_info()]])

def get_lang_info():
	return frappe.cache().get_value("langinfo",
		lambda:frappe.get_file_items(os.path.join(frappe.local.sites_path, "languages.txt")))

def get_dict(fortype, name=None):
	fortype = fortype.lower()
	cache = frappe.cache()
	cache_key = "translation_assets:" + frappe.local.lang
	asset_key = fortype + ":" + (name or "-")
	translation_assets = cache.get_value(cache_key) or {}

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
			messages += frappe.db.sql_list("select name from tabDocType")
			messages += frappe.db.sql_list("select name from tabRole")
			messages += frappe.db.sql_list("select name from `tabModule Def`")

		translation_assets[asset_key] = make_dict_from_messages(messages)
		cache.set_value(cache_key, translation_assets)

	return translation_assets[asset_key]

def add_lang_dict(code):
	messages = extract_messages_from_code(code)
	code += "\n\n$.extend(frappe._messages, %s)" % json.dumps(make_dict_from_messages(messages))
	return code

def make_dict_from_messages(messages, full_dict=None):
	out = {}
	if full_dict==None:
		full_dict = get_full_dict(frappe.local.lang)

	for m in messages:
		if m in full_dict:
			out[m] = full_dict[m]

	return out

def get_lang_js(fortype, name):
	return "\n\n$.extend(frappe._messages, %s)" % json.dumps(get_dict(fortype, name))

def get_full_dict(lang):
	if lang == "en":
		return {}
	return frappe.cache().get_value("lang:" + lang, lambda:load_lang(lang))

def load_lang(lang, apps=None):
	out = {}
	for app in (apps or frappe.get_all_apps(True)):
		path = os.path.join(frappe.get_pymodule_path(app), "translations", lang + ".csv")
		if os.path.exists(path):
			cleaned = dict([item for item in dict(read_csv_file(path)).iteritems() if item[1]])
			out.update(cleaned)

	return out

def clear_cache():
	cache = frappe.cache()
	cache.delete_value("langinfo")
	for lang in get_all_languages():
		cache.delete_value("lang:" + lang)
		cache.delete_value("translation_assets:" + lang)

def get_messages_for_app(app):
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
			messages.append(title or name)
			messages.extend(get_messages_from_page(name))

		# reports
		for name in frappe.db.sql_list("""select tabReport.name from tabDocType, tabReport
			where tabReport.ref_doctype = tabDocType.name
				and tabDocType.module in ({})""".format(modules)):
			messages.append(name)
			messages.extend(get_messages_from_report(name))

	# app_include_files
	messages.extend(get_messages_from_include_files(app))

	# server_messages
	messages.extend(get_server_messages(app))

	return list(set(messages))


def get_messages_from_doctype(name):
	messages = []
	meta = frappe.get_meta(name)

	messages = [meta.name, meta.module]

	if meta.description:
		messages.append(meta.description)

	# translations of field labels, description and options
	for d in meta.get("fields"):
		messages.extend([d.label, d.description])

		if d.fieldtype=='Select' and d.options \
			and not d.options.startswith("attach_files:"):
			options = d.options.split('\n')
			if not "icon" in options[0]:
				messages.extend(options)

	# translations of roles
	for d in meta.get("permissions"):
		if d.role:
			messages.append(d.role)

	# extract from js, py files
	doctype_file_path = frappe.get_module_path(meta.module, "doctype", meta.name, meta.name)
	messages.extend(get_messages_from_file(doctype_file_path + ".js"))
	messages.extend(get_messages_from_file(doctype_file_path + "_list.js"))
	messages.extend(get_messages_from_file(doctype_file_path + "_list.html"))
	messages.extend(get_messages_from_file(doctype_file_path + "_calendar.js"))
	return clean(messages)

def get_messages_from_page(name):
	return get_messages_from_page_or_report("Page", name)

def get_messages_from_report(name):
	report = frappe.get_doc("Report", name)
	messages = get_messages_from_page_or_report("Report", name,
		frappe.db.get_value("DocType", report.ref_doctype, "module"))
	if report.query:
		messages.extend(re.findall('"([^:,^"]*):', report.query))
	messages.append(report.report_name)
	return clean(messages)

def get_messages_from_page_or_report(doctype, name, module=None):
	if not module:
		module = frappe.db.get_value(doctype, name, "module")
	file_path = frappe.get_module_path(module, doctype, name, name)
	messages = get_messages_from_file(file_path + ".js")
	messages += get_messages_from_file(file_path + ".html")
	messages += get_messages_from_file(file_path + ".py")

	return clean(messages)

def get_server_messages(app):
	messages = []
	for basepath, folders, files in os.walk(frappe.get_pymodule_path(app)):
		for dontwalk in (".git", "public", "locale"):
			if dontwalk in folders: folders.remove(dontwalk)

		for f in files:
			if f.endswith(".py") or f.endswith(".html") or f.endswith(".js"):
				messages.extend(get_messages_from_file(os.path.join(basepath, f)))

	return clean(messages)

def get_messages_from_include_files(app_name=None):
	messages = []
	for file in (frappe.get_hooks("app_include_js", app_name=app_name) or []) + (frappe.get_hooks("web_include_js", app_name=app_name) or []):
		messages.extend(get_messages_from_file(os.path.join(frappe.local.sites_path, file)))

	return clean(messages)

def get_messages_from_file(path):
	"""get list of messages from a code file"""
	if os.path.exists(path):
		with open(path, 'r') as sourcefile:
			return extract_messages_from_code(sourcefile.read(), path.endswith(".py"))
	else:
		return []

def extract_messages_from_code(code, is_py=False):
	try:
		code = render_include(code)
	except TemplateError:
		# Exception will occur when it encounters John Resig's microtemplating code
		pass

	messages = []
	messages += re.findall('_\("([^"]*)"', code)
	messages += re.findall("_\('([^']*)'", code)
	if is_py:
		messages += re.findall('_\("{3}([^"]*)"{3}.*\)', code, re.S)
	return clean(messages)

def clean(messages):
	l = []
	messages = list(set(messages))
	for m in messages:
		if m:
			if re.search("[a-z]", m) and not m.startswith("icon-") and not m.endswith("px") and not m.startswith("eval:"):
				l.append(m)
	return l

def read_csv_file(path):
	from csv import reader
	with codecs.open(path, 'r', 'utf-8') as msgfile:
		data = msgfile.read()
		data = reader([r.encode('utf-8') for r in data.splitlines()])
		newdata = [[unicode(val, 'utf-8') for val in row] for row in data]
	return newdata

def write_csv_file(path, app_messages, lang_dict):
	app_messages.sort()
	from csv import writer
	with open(path, 'w') as msgfile:
		w = writer(msgfile)
		for m in app_messages:
			t = lang_dict.get(m, '')
			# strip whitespaces
			t = re.sub('{\s?([0-9]+)\s?}', "{\g<1>}", t)
			w.writerow([m.encode('utf-8'), t.encode('utf-8')])

def get_untranslated(lang, untranslated_file, get_all=False):
	"""translate objects using Google API. Add you own API key for translation"""
	clear_cache()
	apps = frappe.get_all_apps(True)

	messages = []
	untranslated = []
	for app in apps:
		messages.extend(get_messages_for_app(app))

	messages = list(set(messages))

	def escape_newlines(s):
		return (s.replace("\\\n", "|||||")
				.replace("\\n", "||||")
				.replace("\n", "|||"))

	if get_all:
		print str(len(messages)) + " messages"
		with open(untranslated_file, "w") as f:
			for m in messages:
				# replace \n with ||| so that internal linebreaks don't get split
				f.write((escape_newlines(m) + os.linesep).encode("utf-8"))
	else:
		full_dict = get_full_dict(lang)

		for m in messages:
			if not full_dict.get(m):
				untranslated.append(m)

		if untranslated:
			print str(len(untranslated)) + " missing translations of " + str(len(messages))
			with open(untranslated_file, "w") as f:
				for m in untranslated:
					# replace \n with ||| so that internal linebreaks don't get split
					f.write((escape_newlines(m) + os.linesep).encode("utf-8"))
		else:
			print "all translated!"

def update_translations(lang, untranslated_file, translated_file):
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
	for lang in get_all_languages():
		for app in frappe.get_all_apps():
			write_translations_file(app, lang)

def write_translations_file(app, lang, full_dict=None, app_messages=None):
	if not app_messages:
		app_messages = get_messages_for_app(app)

	if not app_messages:
		return

	tpath = frappe.get_pymodule_path(app, "translations")
	frappe.create_folder(tpath)
	write_csv_file(os.path.join(tpath, lang + ".csv"),
		app_messages, full_dict or get_full_dict(lang))

def send_translations(translation_dict):
	"""send these translations in response"""
	if "__messages" not in frappe.local.response:
		frappe.local.response["__messages"] = {}

	frappe.local.response["__messages"].update(translation_dict)
