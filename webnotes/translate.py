# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

from __future__ import unicode_literals

import webnotes, conf
import os
import codecs
import json

messages = {}

def build_message_files():
	"""build from doctypes, pages, database and framework"""
	build_for_pages('lib/core')
	build_for_pages('app')

	build_from_doctype_code('lib/core')
	build_from_doctype_code('app')
	
	# doctype
	build_from_database()
	
	build_for_framework('lib/webnotes', 'py', with_doctype_names=True)
	build_for_framework('lib/public/js/wn', 'js')
	build_for_framework('app/public/js', 'js', with_doctype_names=True)
	
	build_for_modules()

def build_for_pages(path):
	"""make locale files for framework py and js (all)"""
	messages = []
	for (basepath, folders, files) in os.walk(path):
		if os.path.basename(os.path.dirname(basepath))=="page":
			messages_js, messages_py = [], []
			for fname in files:
				if fname.endswith('.js'):
					messages_js += get_message_list(os.path.join(basepath, fname))	
				if fname.endswith('.py'):
					messages_py += get_message_list(os.path.join(basepath, fname))	
			if messages_js:
				write_messages_file(basepath, messages_js, "js")
			if messages_py:
				write_messages_file(basepath, messages_py, "py")

def build_for_modules():
	"""doctype descriptions, module names, etc for each module"""
	from webnotes.modules import get_module_path, get_doc_path
	
	for m in webnotes.conn.sql("""select name from `tabModule Def`"""):
		module_path = get_module_path(m[0])
		if os.path.exists(module_path):
			messages = []
			messages += [t[0] for t in webnotes.conn.sql("""select description from tabDocType 
				where module=%s""", m[0])]
			for t in webnotes.conn.sql("""select 
				if(ifnull(title,'')='',name,title)
				from tabPage where module=%s 
				and ifnull(standard,'No')='Yes' """, m[0]):
				messages.append(t[0])
			messages += [t[0] for t in webnotes.conn.sql("""select t1.name from 
				tabReport t1, tabDocType t2 where
				t1.ref_doctype = t2.name and
				t1.is_standard = "Yes" and
				t2.module = %s""", m[0])]

			doctype_path = get_doc_path(m[0], 'Module Def', m[0])
			write_messages_file(doctype_path, messages, 'doc')

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
	from webnotes.modules import get_doc_path

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
		for fname in files:
			if fname.endswith('.' + mtype):
				messages += get_message_list(os.path.join(basepath, fname))
				
				
	# append module & doctype names
	if with_doctype_names:
		for m in webnotes.conn.sql("""select name, module from `tabDocType`"""):
			messages.append(m[0])
			messages.append(m[1])
	
	if messages:
		write_messages_file(path, messages, mtype)
	
def build_from_doctype_code(path):
	"""walk and make locale files in all folders"""
	for (basepath, folders, files) in os.walk(path):
		messagespy = []
		messagesjs = []
		for fname in files:
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
		messages += re.findall('_\("([^"]*)"\)', txt)
		messages += re.findall("_\('([^']*)'\)", txt)
		messages += re.findall('_\("{3}([^"]*)"{3}\)', txt, re.S)	
		
	return messages
	
def write_messages_file(path, messages, mtype):
	"""write messages to translation file"""
	if not os.path.exists(os.path.join(path, 'locale')):
		os.makedirs(os.path.join(path, 'locale'))
	
	fname = os.path.join(path, 'locale', '_messages_' + mtype + '.json')
	messages = [m.replace("\n", "") for m in filter(None, messages)]
	messages = list(set(messages))
	with open(fname, 'w') as msgfile:
		msgfile.write(json.dumps(messages, indent=1))
		
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

def get_doc_messages(module, doctype, name):
	from webnotes.modules import get_doc_path
	return get_lang_data(get_doc_path(module, doctype, name), None, 'doc')

def get_lang_data(basepath, lang, mtype):
	"""get language dict from langfile"""

	# add "locale" folder if reqd
	if os.path.basename(basepath) != 'locale':
		basepath = os.path.join(basepath, 'locale')
	
	if not lang: lang = webnotes.lang
	
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
		from csv import reader
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
	
	with open(outfile, 'w') as msgfile:
		from csv import writer
		w = writer(msgfile)
		for row in data:
			if not row[1] and row[0] and row[0].strip():
				print 'translating: ' + row[0]
				response = requests.get("""https://www.googleapis.com/language/translate/v2""",
					params = {
						"key": conf.google_api_key,
						"source": "en",
						"target": lang,
						"q": row[0]
					})
			
				row[1] = response.json["data"]["translations"][0]["translatedText"]
				if not row[1]:
					row[1] = row[0] # google unable to translate!
			
			row[0] = row[0].encode('utf-8')
			row[1] = row[1].encode('utf-8')
			w.writerow(row)

