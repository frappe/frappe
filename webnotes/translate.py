# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

"""
Contributing:  
1. Add the .csv file
2. Run import
3. Then run translate
"""

import webnotes
import os
import codecs
import json
import re
from csv import reader
from webnotes.modules import get_doc_path,get_doctype_module
from webnotes.utils import get_base_path, cstr

def translate(lang=None):
	languages = [lang]
	if lang=="all" or lang==None:
		languages = get_all_languages()

	print "Extracting / updating translatable strings..."
	build_message_files()
	
	print "Compiling messages in one file..."
	export_messages(lang, '_lang_tmp.csv')
	
	for lang in languages:
		if lang != "en":
			filename = 'app/translations/'+lang+'.csv'
			print "For " + lang + ":"
			print "Translating via Google Translate..."
			google_translate(lang, '_lang_tmp.csv', filename)
			print "Updating language files..."
			import_messages(lang, filename)
	
	print "Deleting temp file..."
	os.remove('_lang_tmp.csv')

def get_all_languages():
	try:
		return [f[:-4] for f in os.listdir("app/translations") if f.endswith(".csv")]
	except OSError, e:
		if e.args[0]==2:
			return []
		else:
			raise

def get_lang_dict():
	languages_path = os.path.join(get_base_path(), "app", "translations", "languages.json")
	if os.path.exists(languages_path):
		with open(languages_path, "r") as langfile:
			return json.loads(langfile.read())
	else: return {}

def update_translations():
	"""
	compare language file timestamps with last updated timestamps in `.wnf-lang-status`
	if timestamps are missing / changed, build new `.json` files in the `lang folders`
	"""
	langstatus = {}
	languages = get_all_languages()
	message_updated = False
	status_file_path = "app/.wnf-lang-status"
	
	if not os.path.exists(os.path.join('app', 'translations')):
		return
	if os.path.exists(status_file_path):
		with open(status_file_path, "r") as langstatusfile:
			langstatus = eval(langstatusfile.read())
			
	for lang in languages:
		filename = os.path.join('app', 'translations', lang + '.csv')
		if langstatus.get(lang, None)!=os.path.getmtime(filename):
			print "Setting up lang files for " + lang + "..."
			if not message_updated:
				print "Extracting / updating translatable strings..."
				build_message_files()
				message_updated = True
			print "Writing translations..."
			import_messages(lang, filename)
			langstatus[lang] = os.path.getmtime(filename)
	
	with open(status_file_path, "w") as langstatusfile:
		langstatus = langstatusfile.write(str(langstatus))

def build_message_files():
	"""build from doctypes, pages, database and framework"""
	if not webnotes.conn:
		webnotes.connect()
		
	build_for_pages('lib/core')
	build_for_pages('app')

	build_from_doctype_code('lib/core')
	build_from_doctype_code('app')

	#reports
	build_from_query_report()
	
	# doctype
	build_from_database()
	
	build_for_framework('lib/webnotes', 'py', with_doctype_names=True)
	build_for_framework('lib/public/js/wn', 'js')
	build_for_framework('app/public/js', 'js', with_doctype_names=True)
	
def build_for_pages(path):
	"""make locale files for framework py and js (all)"""
	messages = []
	for (basepath, folders, files) in os.walk(path):
		if 'locale' in folders: folders.remove('locale')
		if os.path.basename(os.path.dirname(basepath))=="page":
			messages_js, messages_py = [], []
			for fname in files:
				fname = cstr(fname)
				if fname.endswith('.js'):
					messages_js += get_message_list(os.path.join(basepath, fname))	
				if fname.endswith('.py'):
					messages_py += get_message_list(os.path.join(basepath, fname))	
			if messages_js:
				write_messages_file(basepath, messages_js, "js")
			if messages_py:
				write_messages_file(basepath, messages_py, "py")
	
def build_from_query_report():
	"""make locale for the query reports from database and the framework js and py files"""
	import re
	for item in webnotes.conn.sql("""select name, report_name,ref_doctype, query 
			from `tabReport`""", as_dict=1):
		messages_js, messages_py = [], []

		if item:
			messages_js.append(item.report_name)
			messages_py.append(item.report_name)
			# get the messages from the query using the regex :
			# if we have the string "Production Date:Date:180" in the query then the regex will search for string between " and : .
			# the regex will take "Production Date" and store them into messages
			if item.query :
				messages_query = re.findall('"([^:,^"]*):', item.query)
				messages_js += messages_query
				messages_py += messages_query
			
			module = get_doctype_module(item.ref_doctype)		
			if module :
				doctype_path = get_doc_path(module, "Report", item.name)
				if os.path.exists(doctype_path):
					for (basepath, folders, files) in os.walk(doctype_path):
						if 'locale' in folders: folders.remove('locale')
						for fname in files:
							if fname.endswith('.js'):
								messages_js += get_message_list(os.path.join(basepath, fname))	
							if fname.endswith('.py'):
								messages_py += get_message_list(os.path.join(basepath, fname))
						break			
					write_messages_file(doctype_path, messages_js, 'js')
					write_messages_file(doctype_path, messages_py, 'py')


def build_from_database():
	"""make doctype labels, names, options, descriptions"""
	def get_select_options(doc):
		if doc.doctype=="DocField" and doc.fieldtype=='Select' and doc.options \
			and not doc.options.startswith("link:") \
			and not doc.options.startswith("attach_files:"):
			return doc.options.split('\n')
		else:
			return []

	build_for_doc_from_database(webnotes._dict({
		"doctype": "DocType",
		"module_field": "module",
		"DocType": ["name", "description", "module"],
		"DocField": ["label", "description"],
		"custom": get_select_options
	}))

def build_for_doc_from_database(fields):
	for item in webnotes.conn.sql("""select name from `tab%s`""" % fields.doctype, as_dict=1):
		messages = []
		doclist = webnotes.bean(fields.doctype, item.name).doclist

		for doc in doclist:
			if doc.doctype in fields:
				messages += map(lambda x: x in fields[doc.doctype] and doc.fields.get(x) or None, 
					doc.fields.keys())
					
			if fields.custom:
				messages += fields.custom(doc)	
		
		doc = doclist[0]
		if doc.fields.get(fields.module_field):
			doctype_path = get_doc_path(doc.fields[fields.module_field], 
				doc.doctype, doc.name)
			write_messages_file(doctype_path, messages, 'doc')
	
def build_for_framework(path, mtype, with_doctype_names = False):
	"""make locale files for framework py and js (all)"""
	messages = []
	for (basepath, folders, files) in os.walk(path):
		if 'locale' in folders: folders.remove('locale')
		for fname in files:
			fname = cstr(fname)
			if fname.endswith('.' + mtype):
				messages += get_message_list(os.path.join(basepath, fname))
				
				
	# append module & doctype names
	if with_doctype_names:
		for m in webnotes.conn.sql("""select name, module from `tabDocType`"""):
			messages.append(m[0])
			messages.append(m[1])
			
	# append labels from config.json
	config = webnotes.get_config()
	for moduleinfo in config["modules"].values():
		if moduleinfo.get("label"):
			messages.append(moduleinfo["label"])
	
	if messages:
		write_messages_file(path, messages, mtype)
	
def build_from_doctype_code(path):
	"""walk and make locale files in all folders"""
	for (basepath, folders, files) in os.walk(path):
		messagespy = []
		messagesjs = []
		for fname in files:
			fname = cstr(fname)
			if fname.endswith('py'):
				messagespy += get_message_list(os.path.join(basepath, fname))
			if fname.endswith('js'):
				messagesjs += get_message_list(os.path.join(basepath, fname))

		if messagespy:
			write_messages_file(basepath, messagespy, 'py')

		if messagespy:
			write_messages_file(basepath, messagesjs, 'js')

def get_message_list(path):
	"""get list of messages from a code file"""
	import re
	messages = []
	with open(path, 'r') as sourcefile:
		txt = sourcefile.read()
		messages += re.findall('_\("([^"]*)".*\)', txt)
		messages += re.findall("_\('([^']*)'.*\)", txt)
		messages += re.findall('_\("{3}([^"]*)"{3}.*\)', txt, re.S)	
		
	return messages
	
def write_messages_file(path, messages, mtype):
	"""write messages to translation file"""
	if not os.path.exists(path):
		return
		
	if not os.path.exists(os.path.join(path, 'locale')):
		os.makedirs(os.path.join(path, 'locale'))
	
	fname = os.path.join(path, 'locale', '_messages_' + mtype + '.json')
	messages = list(set(messages))
	filtered = []
	for m in messages:
		if m and re.search('[a-zA-Z]+', m):
			filtered.append(m)
	with open(fname, 'w') as msgfile:
		msgfile.write(json.dumps(filtered, indent=1))
		
def export_messages(lang, outfile):
	"""get list of all messages"""
	messages = {}
	# extract messages
	for (basepath, folders, files) in os.walk('.'):
		def _get_messages(messages, basepath, mtype):
			mlist = get_messages(basepath, mtype)
			if not mlist:
				return
								
			# update messages with already existing translations
			langdata = get_lang_data(basepath, lang, mtype)
			for m in mlist:
				if not messages.get(m):
					messages[m] = langdata.get(m, "")
		
		if os.path.basename(basepath)=='locale':
			_get_messages(messages, basepath, 'doc')
			_get_messages(messages, basepath, 'py')
			_get_messages(messages, basepath, 'js')
				
	# remove duplicates
	if outfile:
		from csv import writer
		with open(outfile, 'w') as msgfile:
			w = writer(msgfile)
			keys = messages.keys()
			keys.sort()
			for m in keys:
				
				w.writerow([m.encode('utf-8'), messages.get(m, '').encode('utf-8')])
	
def import_messages(lang, infile):
	"""make individual message files for each language"""
	data = dict(get_all_messages_from_file(infile))
		
	for (basepath, folders, files) in os.walk('.'):
		def _update_lang_file(mtype):
			"""create a langauge file for the given message type"""
			messages = get_messages(basepath, mtype)
			if not messages: return

			# read existing
			langdata = get_lang_data(basepath, lang, mtype)
							
			# update fresh
			for m in messages:				
				if data.get(m):
					langdata[m] = data.get(m)
			
			if langdata:
				# write new langfile
				langfilename = os.path.join(basepath, lang + '-' + mtype + '.json')
				with open(langfilename, 'w') as langfile:
					langfile.write(json.dumps(langdata, indent=1, sort_keys=True).encode('utf-8'))
				#print 'wrote ' + langfilename
				
		if os.path.basename(basepath)=='locale':
			# make / update lang files for each type of message file (doc, js, py)
			# example: hi-doc.json, hi-js.json, hi-py.json
			_update_lang_file('doc')
			_update_lang_file('js')
			_update_lang_file('py')

def load_doc_messages(module, doctype, name):
	if webnotes.lang=="en":
		return {}

	if not webnotes.local.translated_docs:
		webnotes.local.translated_docs = []

	doc_path = get_doc_path(module, doctype, name)

	# don't repload the same doc again
	if (webnotes.lang + ":" + doc_path) in webnotes.local.translated_docs:
		return

	if not docs_loaded:
		webnotes.local.translate_docs_loaded = []
	webnotes.local.translated_docs.append(webnotes.lang + ":" + doc_path)

	webnotes.local.translations.update(get_lang_data(doc_path, None, 'doc'))

def get_lang_data(basepath, lang, mtype):
	"""get language dict from langfile"""

	# add "locale" folder if reqd
	if os.path.basename(basepath) != 'locale':
		basepath = os.path.join(basepath, 'locale')
	
	if not lang: lang = webnotes.local.lang
	
	path = os.path.join(basepath, lang + '-' + mtype + '.json')
		
	langdata = {}
	if os.path.exists(path):
		with codecs.open(path, 'r', 'utf-8') as langfile:
			langdata = json.loads(langfile.read())

	return langdata

def get_messages(basepath, mtype):
	"""load list of messages from _message files"""
	# get message list
	path = os.path.join(basepath, '_messages_' + mtype + '.json')
	messages = []
	if os.path.exists(path):
		with open(path, 'r') as msgfile:
			messages = json.loads(msgfile.read())
			
	return messages

def update_lang_js(jscode, path):
	return jscode + "\n\n$.extend(wn._messages, %s)" % \
		json.dumps(get_lang_data(path, webnotes.lang, 'js'))
		
def get_all_messages_from_file(path):
	with codecs.open(path, 'r', 'utf-8') as msgfile:
		data = msgfile.read()
		data = reader([r.encode('utf-8') for r in data.splitlines()])
		newdata = []
		for row in data:
			newrow = []
			for val in row:
				newrow.append(unicode(val, 'utf-8'))
			newdata.append(newrow)

	return newdata

def google_translate(lang, infile, outfile):
	"""translate objects using Google API. Add you own API key for translation"""
	data = get_all_messages_from_file(infile)
		
	import requests
	from webnotes import conf
	
	old_translations = {}
	
	# update existing translations
	if os.path.exists(outfile):
		with codecs.open(outfile, "r", "utf-8") as oldfile:
			old_data = oldfile.read()
			old_translations = dict(reader([r.encode('utf-8').strip() for r in old_data.splitlines()]))
		
	with open(outfile, 'w') as msgfile:
		from csv import writer
		w = writer(msgfile)
		for row in data:
			if row[0] and row[0].strip():
				if old_translations.get(row[0].strip()):
					row[1] = old_translations[row[0].strip()]
				else:
					print 'translating: ' + row[0]
					response = requests.get("""https://www.googleapis.com/language/translate/v2""",
						params = {
							"key": conf.google_api_key,
							"source": "en",
							"target": lang,
							"q": row[0]
						})
			
					if "error" in response.json:
						print response.json
						continue
					
					row[1] = response.json["data"]["translations"][0]["translatedText"]
					if not row[1]:
						row[1] = row[0] # google unable to translate!
			
					row[1] = row[1].encode('utf-8')

				row[0] = row[0].encode('utf-8')
				w.writerow(row)

