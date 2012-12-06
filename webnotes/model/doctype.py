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

"""
Get metadata (main doctype with fields and permissions with all table doctypes)

- if exists in cache, get it from cache
- add custom fields
- override properties from PropertySetter
- sort based on prev_field
- optionally, post process (add js, css, select fields), or without

"""
from __future__ import unicode_literals

# imports
import conf
import webnotes
import webnotes.model
import webnotes.model.doc
import webnotes.model.doclist

doctype_cache = {}
docfield_types = None

def get(doctype, processed=False, cached=True):
	"""return doclist"""
	if cached:
		doclist = from_cache(doctype, processed)
		if doclist: return DocTypeDocList(doclist)
	
	load_docfield_types()
	
	# main doctype doclist
	doclist = get_doctype_doclist(doctype)

	# add doctypes of table fields
	table_types = [d.options for d in doclist \
		if d.doctype=='DocField' and d.fieldtype=='Table']
		
	for table_doctype in table_types:
		doclist += get_doctype_doclist(table_doctype)
		
	if processed: 
		add_code(doctype, doclist)
		expand_selects(doclist)
		add_print_formats(doclist)
		add_search_fields(doclist)
		add_linked_with(doclist)
		#add_workflows(doclist)
		#update_language(doclist)

	# add validators
	#add_validators(doctype, doclist)
	
	# add precision
	add_precision(doctype, doclist)

	to_cache(doctype, processed, doclist)
		
	return DocTypeDocList(doclist)

def load_docfield_types():
	global docfield_types
	docfield_types = dict(webnotes.conn.sql("""select fieldname, fieldtype from tabDocField
		where parent='DocField'"""))

def add_workflows(doclist):
	from webnotes.model.workflow import get_workflow_name
	doctype = doclist[0].name
	
	# get active workflow
	workflow_name = get_workflow_name(doctype)

	if workflow_name and webnotes.conn.exists("Workflow", workflow_name):
		doclist += webnotes.get_doclist("Workflow", workflow_name)
		
		# add workflow states (for icons and style)
		for state in map(lambda d: d.state, doclist.get({"doctype":"Workflow Document State"})):
			doclist += webnotes.get_doclist("Workflow State", state)
	
def get_doctype_doclist(doctype):
	"""get doclist of single doctype"""
	doclist = webnotes.get_doclist('DocType', doctype)
	add_custom_fields(doctype, doclist)
	apply_property_setters(doctype, doclist)
	sort_fields(doclist)
	return doclist

def sort_fields(doclist):
	"""sort on basis of previous_field"""
	from webnotes.model.doclist import DocList
	newlist = DocList([])
	pending = filter(lambda d: d.doctype=='DocField', doclist)
	
	maxloops = 20
	while (pending and maxloops>0):
		maxloops -= 1
		for d in pending[:]:
			if d.previous_field:
				# field already added
				for n in newlist:
					if n.fieldname==d.previous_field:
						newlist.insert(newlist.index(n)+1, d)
						pending.remove(d)
						break
			else:
				newlist.append(d)
				pending.remove(d)
			
	# recurring at end	
	if pending:
		newlist += pending
		
	# renum
	idx = 1
	for d in newlist:
		d.idx = idx
		idx += 1

	doclist.get({"doctype":["!=", "DocField"]}).extend(newlist)
			
def apply_property_setters(doctype, doclist):		
	from webnotes.utils import cint
	for ps in webnotes.conn.sql("""select * from `tabProperty Setter` where
		doc_type=%s""", doctype, as_dict=1):
		if ps['doctype_or_field']=='DocType':
			doclist[0].fields[ps['property']] = ps['value']
		else:
			docfield = filter(lambda d: d.doctype=="DocField" and d.fieldname==ps['field_name'], 
				doclist)
			if not docfield: continue
			if docfield_types.get(ps['property'], None) in ('Int', 'Check'):
				ps['value'] = cint(ps['value'])
				
			docfield[0].fields[ps['property']] = ps['value']

def add_custom_fields(doctype, doclist):
	try:
		res = webnotes.conn.sql("""SELECT * FROM `tabCustom Field`
			WHERE dt = %s AND docstatus < 2""", doctype, as_dict=1)
	except Exception, e:
		if e.args[0]==1146:
			return doclist
		else:
			raise e

	for r in res:
		custom_field = webnotes.model.doc.Document(fielddata=r)
		
		# convert to DocField
		custom_field.fields.update({
			'doctype': 'DocField',
			'parent': doctype,
			'parentfield': 'fields',
			'parenttype': 'DocType',
		})
		doclist.append(custom_field)

	return doclist

def add_linked_with(doclist):
	"""add list of doctypes this doctype is 'linked' with"""
	doctype = doclist[0].name
	links = webnotes.conn.sql("""select parent, fieldname from tabDocField
		where (fieldtype="Link" and options=%s)
		or (fieldtype="Select" and options=%s)""", (doctype, "link:"+ doctype))
	links += webnotes.conn.sql("""select dt, fieldname from `tabCustom Field`
		where (fieldtype="Link" and options=%s)
		or (fieldtype="Select" and options=%s)""", (doctype, "link:"+ doctype))
		
	doclist[0].fields["__linked_with"] = dict(list(set(links)))

def from_cache(doctype, processed):
	""" load doclist from cache.
		sets flag __from_cache in first doc of doclist if loaded from cache"""
	
	global doctype_cache

	# from memory
	if not processed and doctype in doctype_cache:
		return doctype_cache[doctype]

	doclist = webnotes.cache().get_value(cache_name(doctype, processed))
	if doclist:
		import json
		from webnotes.model.doclist import DocList
		doclist = DocList([webnotes.model.doc.Document(fielddata=d)
				for d in doclist])
		doclist[0].fields["__from_cache"] = 1
		return doclist

def to_cache(doctype, processed, doclist):
	global doctype_cache
	import json
	from webnotes.handler import json_handler
	
	webnotes.cache().set_value(cache_name(doctype, processed), 
		[d.fields for d in doclist])

	if not processed:
		doctype_cache[doctype] = doclist

def cache_name(doctype, processed):
	"""returns cache key"""
	suffix = ""
	if processed:
		suffix = ":Raw"
	return "doctype:" + doctype + suffix

def clear_cache(doctype):
	global doctype_cache

	def clear_single(dt):
		webnotes.cache().delete_value(cache_name(dt, False))
		webnotes.cache().delete_value(cache_name(dt, True))

		if doctype in doctype_cache:
			del doctype_cache[dt]
			
	clear_single(doctype)
	
	# clear all parent doctypes
	for dt in webnotes.conn.sql("""select parent from tabDocField 
		where fieldtype="Table" and options=%s""", doctype):
		clear_single(dt[0])

def add_code(doctype, doclist):
	import os, conf
	from webnotes.modules import scrub, get_module_path
	
	doc = doclist[0]
	
	path = os.path.join(get_module_path(doc.module), 'doctype', scrub(doc.name))

	def _add_code(fname, fieldname):
		fpath = os.path.join(path, fname)
		if os.path.exists(fpath):
			with open(fpath, 'r') as f:
				doc.fields[fieldname] = f.read()
		
	_add_code(scrub(doc.name) + '.js', '__js')
	_add_code(scrub(doc.name) + '.css', '__css')
	_add_code('%s_list.js' % scrub(doc.name), '__listjs')
	add_embedded_js(doc)
	
def add_embedded_js(doc):
	"""embed all require files"""

	import re, os, conf

	# custom script
	custom = webnotes.conn.get_value("Custom Script", {"dt": doc.name, 
		"script_type": "Client"}, "script") or ""
	doc.fields['__js'] = (doc.fields.get('__js') or '') + '\n' + custom	
	
	def _sub(match):
		fpath = os.path.join(os.path.dirname(conf.__file__), \
			re.search('["\'][^"\']*["\']', match.group(0)).group(0)[1:-1])
		if os.path.exists(fpath):
			with open(fpath, 'r') as f:
				return '\n' + f.read() + '\n'
		else:
			return '\n// no file "%s" found \n' % fpath
	
	if doc.fields.get('__js'):
		doc.fields['__js'] = re.sub('(wn.require\([^\)]*.)', _sub, doc.fields['__js'])
		
def expand_selects(doclist):
	for d in filter(lambda d: d.fieldtype=='Select' \
		and (d.options or '').startswith('link:'), doclist):
		doctype = d.options.split("\n")[0][5:]
		d.options = '\n'.join([''] + [o.name for o in webnotes.conn.sql("""select 
			name from `tab%s` where docstatus<2 order by name asc""" % doctype, as_dict=1)])

def add_print_formats(doclist):
	print_formats = webnotes.conn.sql("""select * FROM `tabPrint Format`
		WHERE doc_type=%s AND docstatus<2""", doclist[0].name, as_dict=1)
	for pf in print_formats:
		doclist.append(webnotes.model.doc.Document('Print Format', fielddata=pf))

def get_property(dt, prop, fieldname=None):
	"""get a doctype property"""
	doctypelist = get(dt)
	if fieldname:
		field = doctypelist.get_field(fieldname)
		return field and field.fields.get(prop) or None
	else:
		return doctypelist[0].fields.get(prop)
		
def get_link_fields(doctype):
	"""get docfields of links and selects with "link:" """
	doctypelist = get(doctype)
	
	return doctypelist.get({"fieldtype":"Link"}).extend(doctypelist.get({"fieldtype":"Select", 
		"options": "^link:"}))
		
def add_validators(doctype, doclist):
	for validator in webnotes.conn.sql("""select name from `tabDocType Validator` where
		for_doctype=%s""", doctype, as_dict=1):
		doclist.extend(webnotes.get_doclist('DocType Validator', validator.name))
		
def add_search_fields(doclist):
	"""add search fields found in the doctypes indicated by link fields' options"""
	for lf in doclist.get({"fieldtype": "Link", "options":["!=", "[Select]"]}):
		if lf.options:
			search_fields = get(lf.options)[0].search_fields
			if search_fields:
				lf.search_fields = map(lambda sf: sf.strip(), search_fields.split(","))

def update_language(doclist):
	"""update language"""
	if webnotes.lang != 'en':
		from webnotes import _
		from webnotes.modules import get_doc_path

		# load languages for each doctype
		from webnotes.translate import get_lang_data, update_lang_js
		_messages = {}

		for d in doclist:
			if d.doctype=='DocType':
				_messages.update(get_lang_data(get_doc_path(d.module, d.doctype, d.name), 
					webnotes.lang, 'doc'))
				_messages.update(get_lang_data(get_doc_path(d.module, d.doctype, d.name), 
					webnotes.lang, 'js'))

		doc = doclist[0]

		# attach translations to client
		doc.fields["__messages"] = _messages

def add_precision(doctype, doclist):
	type_precision_map = {
		"Currency": 2,
		"Float": 4
	}
	for df in doclist.get({"doctype": "DocField", 
			"fieldtype": ["in", type_precision_map.keys()]}):
		df.precision = type_precision_map[df.fieldtype]

class DocTypeDocList(webnotes.model.doclist.DocList):
	def get_field(self, fieldname, parent=None, parentfield=None):
		filters = {"doctype":"DocField"}
		if isinstance(fieldname, dict):
			filters.update(fieldname)
		else:
			filters["fieldname"] = fieldname
		
		# if parentfield, get the name of the parent table
		if parentfield:
			parent = self.get_options(parentfield)

		if parent:
			filters["parent"] = parent
		else:
			filters["parent"] = self[0].name
		
		fields = self.get(filters)
		if fields:
			return fields[0]
		
	def get_fieldnames(self, filters=None):
		if not filters: filters = {}
		filters.update({"doctype": "DocField", "parent": self[0].name})
			
		return map(lambda df: df.fieldname, self.get(filters))
	
	def get_options(self, fieldname, parent=None, parentfield=None):
		return self.get_field(fieldname, parent, parentfield).options
		
	def get_label(self, fieldname, parent=None, parentfield=None):
		return self.get_field(fieldname, parent, parentfield).label
		
	def get_table_fields(self):
		return self.get({"doctype": "DocField", "fieldtype": "Table"})
		
	def get_precision_map(self, parent=None, parentfield=None):
		"""get a map of fields of type 'currency' or 'float' with precision values"""
		filters = {"doctype": "DocField", "fieldtype": ["in", ["Currency", "Float"]]}
		if parentfield:
			parent = self.get_options(parentfield)
		if parent:
			filters["parent"] = parent
		else:
			filters["parent"] = self[0].name
		
		from webnotes import DictObj
		return DictObj((f.fieldname, f.precision) for f in self.get(filters))
		
	def get_parent_doclist(self):
		return webnotes.doclist([self[0]] + self.get({"parent": self[0].name}))

def rename_field(doctype, old_fieldname, new_fieldname, lookup_field=None):
	"""this function assumes that sync is NOT performed"""
	import webnotes.model
	doctype_list = get(doctype)
	old_field = doctype_list.get_field(lookup_field or old_fieldname)
	if not old_field:
		print "rename_field: " + (lookup_field or old_fieldname) + " not found."
		
		
	if old_field.fieldtype == "Table":
		# change parentfield of table mentioned in options
		webnotes.conn.sql("""update `tab%s` set parentfield=%s
			where parentfield=%s""" % (old_field.options.split("\n")[0], "%s", "%s"),
			(new_fieldname, old_fieldname))
	elif old_field.fieldtype not in webnotes.model.no_value_fields:
		# copy
		if doctype_list[0].issingle:
			webnotes.conn.sql("""update `tabSingles` set field=%s
				where doctype=%s and field=%s""", 
				(new_fieldname, doctype, old_fieldname))
		else:
			webnotes.conn.sql("""update `tab%s` set `%s`=`%s`""" % \
				(doctype, new_fieldname, old_fieldname))	
