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
# wn.require
# webnotes._

import webnotes, os, re, codecs, json

def get_all_languages():
	return [a.split()[0] for a in get_lang_info()]

def get_lang_dict():
	return dict([[a[1], a[0]] for a in [a.split() for a in get_lang_info()]])
	
def get_lang_info():
	return webnotes.cache().get_value("langinfo", 
		lambda:webnotes.get_file_items(os.path.join(webnotes.local.sites_path, "languages.txt")))
	
def rebuild_all_translation_files():
	for lang in get_all_languages():
		for app in get_all_apps():
			write_translations_file(app, lang)
	
def write_translations_file(app, lang, full_dict=None):
	tpath = webnotes.get_pymodule_path(app, "translations")
	webnotes.create_folder(tpath)
	write_csv_file(os.path.join(tpath, lang + ".csv"),
		get_messages_for_app(app), full_dict or get_full_dict(lang))

def get_dict(fortype, name=None):
	fortype = fortype.lower()
	cache = webnotes.cache()
	cache_key = "translation_assets:" + webnotes.local.lang
	asset_key = fortype + ":" + name
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
		
		translation_assets[asset_key] = make_dict_from_messages(messages)
		cache.set_value(cache_key, translation_assets)
		
	return translation_assets[asset_key]
	
def add_lang_dict(code):
	messages = extract_messages_from_code(code)
	code += "\n\n$.extend(wn._messages, %s)" % json.dumps(make_dict_from_messages(messages))
	return code

def make_dict_from_messages(messages, full_dict=None):
	out = {}
	if full_dict==None:
		full_dict = get_full_dict(webnotes.local.lang)
	
	for m in messages:
		if m in full_dict:
			out[m] = full_dict[m]
				
	return out

def get_lang_js(fortype, name):
	return "\n\n$.extend(wn._messages, %s)" % json.dumps(get_dict(fortype, name))

def get_full_dict(lang):
	if lang == "en": return {}
	return webnotes.cache().get_value("lang:" + lang, lambda:load_lang(lang))

def load_lang(lang, apps=None):
	out = {}
	for app in (apps or webnotes.get_all_apps(True)):
		path = webnotes.get_pymodule_path(app, "translations", lang + ".csv")
		if os.path.exists(path):
			cleaned = dict([item for item in dict(read_csv_file(path)).iteritems() if item[1]])
			out.update(cleaned)
	return out
	
def clear_cache():
	cache = webnotes.cache()
	cache.delete_value("langinfo")
	for lang in get_all_languages():
		cache.delete_value("lang:" + lang)
		cache.delete_value("translation_assets:" + lang)
	
def get_messages_for_app(app):
	messages = []
	modules = ", ".join(['"{}"'.format(m.title().replace("_", " ")) \
		for m in webnotes.local.app_modules[app]])
			
	# doctypes
	for name in webnotes.conn.sql_list("""select name from tabDocType 
		where module in ({})""".format(modules)):
		messages.extend(get_messages_from_doctype(name))

	# pages
	for name in webnotes.conn.sql_list("""select name from tabPage 
		where module in ({})""".format(modules)):
		messages.extend(get_messages_from_page(name))
	
	# reports
	for name in webnotes.conn.sql_list("""select tabReport.name from tabDocType, tabReport 
		where tabReport.ref_doctype = tabDocType.name 
			and tabDocType.module in ({})""".format(modules)):
		messages.extend(get_messages_from_report(name))
	
	# app_include_files
	messages.extend(get_messages_from_include_files(app))

	# server_messages
	messages.extend(get_server_messages(app))

	return list(set(messages))


def get_messages_from_doctype(name):
	messages = []
	meta = webnotes.get_doctype(name)
	
	messages = [meta[0].name, meta[0].description, meta[0].module]
	
	for d in meta.get({"doctype":"DocField"}):
		messages.extend([d.label, d.description])
		
		if d.fieldtype=='Select' and d.options \
			and not d.options.startswith("link:") \
			and not d.options.startswith("attach_files:"):
			options = d.options.split('\n')
			if not "icon" in options[0]:
				messages.extend(options)
				
	# extract from js, py files
	doctype_file_path = webnotes.get_module_path(meta[0].module, "doctype", meta[0].name, meta[0].name)
	messages.extend(get_messages_from_file(doctype_file_path + ".js"))
	return clean(messages)
	
def get_messages_from_page(name):
	return get_messages_from_page_or_report("Page", name)
	
def get_messages_from_report(name):
	report = webnotes.doc("Report", name)
	messages = get_messages_from_page_or_report("Report", name, 
		webnotes.conn.get_value("DocType", report.ref_doctype, "module"))
	if report.query:
		messages.extend(re.findall('"([^:,^"]*):', report.query))
		messages.append(report.report_name)
	return clean(messages)

def get_messages_from_page_or_report(doctype, name, module=None):
	if not module:
		module = webnotes.conn.get_value(doctype, name, "module")
	file_path = webnotes.get_module_path(module, doctype, name, name)
	messages = get_messages_from_file(file_path + ".js")
	
	return clean(messages)
	
def get_server_messages(app):
	messages = []
	for basepath, folders, files in os.walk(webnotes.get_pymodule_path(app)):
		for dontwalk in (".git", "public", "locale"):
			if dontwalk in folders: folders.remove(dontwalk)
		
		for f in files:
			if f.endswith(".py") or f.endswith(".html"):
				messages.extend(get_messages_from_file(os.path.join(basepath, f)))

	return clean(messages)
	
def get_messages_from_include_files(app_name=None):
	messages = []
	hooks = webnotes.get_hooks(app_name)
	for file in (hooks.app_include_js or []) + (hooks.web_include_js or []):
		messages.extend(get_messages_from_file(os.path.join(webnotes.local.sites_path, file)))
		
	return messages
	
def get_messages_from_file(path):
	"""get list of messages from a code file"""
	if os.path.exists(path):
		with open(path, 'r') as sourcefile:
			return extract_messages_from_code(sourcefile.read(), path.endswith(".py"))
	else:
		return []

def extract_messages_from_code(code, is_py=False):
	messages = []
	messages += re.findall('_\("([^"]*)"\)', code)
	messages += re.findall("_\('([^']*)'\)", code)
	if is_py:
		messages += re.findall('_\("{3}([^"]*)"{3}.*\)', code, re.S)	
	return messages
	
def clean(messages):
	return filter(lambda t: t if t else None, list(set(messages)))

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
			w.writerow([m.encode('utf-8'), lang_dict.get(m, '').encode('utf-8')])
	
def get_untranslated(lang, untranslated_file):
	"""translate objects using Google API. Add you own API key for translation"""	
	clear_cache()
	apps = webnotes.get_all_apps(True)
	
	messages = []
	untranslated = []
	for app in apps:
		messages.extend(get_messages_for_app(app))
	
	full_dict = get_full_dict(lang)
	
	for m in messages:
		if not full_dict.get(m):
			untranslated.append(m)
	
	if untranslated:
		print str(len(untranslated)) + " missing translations of " + str(len(messages))
		with open(untranslated_file, "w") as f:
			f.write("\n".join(untranslated))
	else:
		print "all translated!"

def update_translations(lang, untranslated_file, translated_file):
	clear_cache()
	full_dict = get_full_dict(lang)
	
	full_dict.update(dict(zip(webnotes.get_file_items(untranslated_file), 
		webnotes.get_file_items(translated_file))))

	for app in webnotes.get_all_apps(True):
		write_translations_file(app, lang, full_dict)
			
def google_translate(lang, untranslated):
	import requests
	if untranslated:
		response = requests.get("""https://www.googleapis.com/language/translate/v2""",
			params = {
				"key": webnotes.conf.google_api_key,
				"source": "en",
				"target": lang,
				"q": "\n".join(untranslated)
			})
			
		data = response.json()

		if "error" in data:
			print data

		translated = data["data"]["translations"][0]["translatedText"]
		if translated:
			return dict(zip(untranslated, translated))
		else:
			print "unable to translate"
			return {}