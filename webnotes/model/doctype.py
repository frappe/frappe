# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

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
import webnotes
import webnotes.model
import webnotes.model.doc
import webnotes.model.doclist
from webnotes.utils import cint, get_base_path

doctype_cache = webnotes.local('doctype_doctype_cache')
docfield_types = webnotes.local('doctype_docfield_types')

# doctype_cache = {}
# docfield_types = None

def get(doctype, processed=False, cached=True):
	"""return doclist"""
	if cached:
		doclist = from_cache(doctype, processed)
		if doclist: 
			if processed:
				update_language(doclist)
			return DocTypeDocList(doclist)
	
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
		add_workflows(doclist)
		add_linked_with(doclist)
	
	to_cache(doctype, processed, doclist)

	if processed:
		update_language(doclist)

	return DocTypeDocList(doclist)

def load_docfield_types():
	webnotes.local.doctype_docfield_types = dict(webnotes.conn.sql("""select fieldname, fieldtype from tabDocField
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
	for ps in webnotes.conn.sql("""select * from `tabProperty Setter` where
		doc_type=%s""", doctype, as_dict=1):
		if ps['doctype_or_field']=='DocType':
			if ps.get('property_type', None) in ('Int', 'Check'):
				ps['value'] = cint(ps['value'])
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
			raise

	for r in res:
		custom_field = webnotes.model.doc.Document(fielddata=r)
		
		# convert to DocField
		custom_field.fields.update({
			'doctype': 'DocField',
			'parent': doctype,
			'parentfield': 'fields',
			'parenttype': 'DocType',
			'__custom_field': 1
		})
		doclist.append(custom_field)

	return doclist

def add_linked_with(doclist):
	"""add list of doctypes this doctype is 'linked' with"""
	doctype = doclist[0].name
	links = webnotes.conn.sql("""select parent, fieldname from tabDocField
		where (fieldtype="Link" and options=%s)
		or (fieldtype="Select" and options=%s)""", (doctype, "link:"+ doctype))
	links += webnotes.conn.sql("""select dt as parent, fieldname from `tabCustom Field`
		where (fieldtype="Link" and options=%s)
		or (fieldtype="Select" and options=%s)""", (doctype, "link:"+ doctype))

	links = dict(links)

	if not links: 
		return {}

	ret = {}

	for dt in links:
		ret[dt] = { "fieldname": links[dt] }

	for grand_parent, options in webnotes.conn.sql("""select parent, options from tabDocField 
		where fieldtype="Table" 
			and options in (select name from tabDocType 
				where istable=1 and name in (%s))""" % ", ".join(["%s"] * len(links)) ,tuple(links)):

		ret[grand_parent] = {"child_doctype": options, "fieldname": links[options] }
		if options in ret:
			del ret[options]
		
	doclist[0].fields["__linked_with"] = ret

def from_cache(doctype, processed):
	""" load doclist from cache.
		sets flag __from_cache in first doc of doclist if loaded from cache"""

	# from memory
	if doctype_cache and not processed and doctype in doctype_cache:
		return doctype_cache[doctype]

	doclist = webnotes.cache().get_value(cache_name(doctype, processed))
	if doclist:
		from webnotes.model.doclist import DocList
		doclist = DocList([webnotes.model.doc.Document(fielddata=d)
				for d in doclist])
		doclist[0].fields["__from_cache"] = 1
		return doclist

def to_cache(doctype, processed, doclist):

	if not doctype_cache:
		webnotes.local.doctype_doctype_cache = {}

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

def clear_cache(doctype=None):
	def clear_single(dt):
		webnotes.cache().delete_value(cache_name(dt, False))
		webnotes.cache().delete_value(cache_name(dt, True))

		if doctype_cache and doctype in doctype_cache:
			del doctype_cache[dt]

	if doctype:
		clear_single(doctype)
	
		# clear all parent doctypes
		for dt in webnotes.conn.sql("""select parent from tabDocField 
			where fieldtype="Table" and options=%s""", doctype):
			clear_single(dt[0])
		
		# clear all notifications
		from webnotes.core.doctype.notification_count.notification_count import delete_notification_count_for
		delete_notification_count_for(doctype)
		
	else:
		# clear all
		for dt in webnotes.conn.sql("""select name from tabDocType"""):
			clear_single(dt[0])

def add_code(doctype, doclist):
	import os
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
	_add_code('%s_list.js' % scrub(doc.name), '__list_js')
	_add_code('%s_calendar.js' % scrub(doc.name), '__calendar_js')
	_add_code('%s_map.js' % scrub(doc.name), '__map_js')
	add_embedded_js(doc)
	
def add_embedded_js(doc):
	"""embed all require files"""

	import re, os
	from webnotes import conf

	js = doc.fields.get('__js') or ''

	# custom script
	custom = webnotes.conn.get_value("Custom Script", {"dt": doc.name, 
		"script_type": "Client"}, "script") or ""
	js = (js + '\n' + custom).encode("utf-8")

	if "{% include" in js:
		js = webnotes.get_jenv().from_string(js).render()
	
	doc.fields["__js"] = js
			
def expand_selects(doclist):
	for d in filter(lambda d: d.fieldtype=='Select' \
		and (d.options or '').startswith('link:'), doclist):
		doctype = d.options.split("\n")[0][5:]
		d.link_doctype = doctype
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
		doclist[0].fields["__messages"] = webnotes.get_lang_dict("doctype", doclist[0].name)

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
