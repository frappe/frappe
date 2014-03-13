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
import json, os
import frappe
import frappe.model
import frappe.model.doc
import frappe.model.doclist
from frappe.utils import cint, cstr

doctype_cache = frappe.local('doctype_doctype_cache')
docfield_types = frappe.local('doctype_docfield_types')

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
	frappe.local.doctype_docfield_types = dict(frappe.db.sql("""select fieldname, fieldtype from tabDocField
		where parent='DocField'"""))

def add_workflows(doclist):
	from frappe.model.workflow import get_workflow_name
	doctype = doclist[0].name
	
	# get active workflow
	workflow_name = get_workflow_name(doctype)

	if workflow_name and frappe.db.exists("Workflow", workflow_name):
		doclist += frappe.get_doclist("Workflow", workflow_name)
		
		# add workflow states (for icons and style)
		for state in map(lambda d: d.state, doclist.get({"doctype":"Workflow Document State"})):
			doclist += frappe.get_doclist("Workflow State", state)
	
def get_doctype_doclist(doctype):
	"""get doclist of single doctype"""
	doclist = frappe.get_doclist('DocType', doctype)
	add_custom_fields(doctype, doclist)
	apply_property_setters(doctype, doclist)
	sort_fields(doclist)
	return doclist

def sort_fields(doclist):
	"""sort on basis of previous_field"""

	from frappe.model.doclist import DocList
	newlist = DocList([])
	pending = doclist.get({"doctype":"DocField"})

	if doclist[0].get("_idx"):
		for fieldname in json.loads(doclist[0].get("_idx")):
			d = doclist.get({"fieldname": fieldname})
			if d:
				newlist.append(d[0])
				pending.remove(d[0])
	else:
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
	for ps in frappe.db.sql("""select * from `tabProperty Setter` where
		doc_type=%s""", (doctype,), as_dict=1):
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
		res = frappe.db.sql("""SELECT * FROM `tabCustom Field`
			WHERE dt = %s AND docstatus < 2""", (doctype,), as_dict=1)
	except Exception, e:
		if e.args[0]==1146:
			return doclist
		else:
			raise

	for r in res:
		custom_field = frappe.model.doc.Document(fielddata=r)
		
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
	links = frappe.db.sql("""select parent, fieldname from tabDocField
		where (fieldtype="Link" and options=%s)
		or (fieldtype="Select" and options=%s)""", (doctype, "link:"+ doctype))
	links += frappe.db.sql("""select dt as parent, fieldname from `tabCustom Field`
		where (fieldtype="Link" and options=%s)
		or (fieldtype="Select" and options=%s)""", (doctype, "link:"+ doctype))

	links = dict(links)

	if not links: 
		return {}

	ret = {}

	for dt in links:
		ret[dt] = { "fieldname": links[dt] }

	for grand_parent, options in frappe.db.sql("""select parent, options from tabDocField 
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
		doclist = doctype_cache[doctype]
		doclist[0].fields["__from_cache"] = 1
		return doclist

	doclist = frappe.cache().get_value(cache_name(doctype, processed))
	if doclist:
		from frappe.model.doclist import DocList
		doclist = DocList([frappe.model.doc.Document(fielddata=d)
				for d in doclist])
		doclist[0].fields["__from_cache"] = 1
		return doclist

def to_cache(doctype, processed, doclist):

	if not doctype_cache:
		frappe.local.doctype_doctype_cache = {}

	frappe.cache().set_value(cache_name(doctype, processed), 
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
		frappe.cache().delete_value(cache_name(dt, False))
		frappe.cache().delete_value(cache_name(dt, True))

		if doctype_cache and (dt in doctype_cache):
			del doctype_cache[dt]

	if doctype:
		clear_single(doctype)
	
		# clear all parent doctypes
		for dt in frappe.db.sql("""select parent from tabDocField 
			where fieldtype="Table" and options=%s""", (doctype,)):
			clear_single(dt[0])
		
		# clear all notifications
		from frappe.core.doctype.notification_count.notification_count import delete_notification_count_for
		delete_notification_count_for(doctype)
		
	else:
		# clear all
		for dt in frappe.db.sql("""select name from tabDocType"""):
			clear_single(dt[0])

def add_code(doctype, doclist):
	import os
	from frappe.modules import scrub, get_module_path
	
	doc = doclist[0]
	
	path = os.path.join(get_module_path(doc.module), 'doctype', scrub(doc.name))
	def _get_path(fname):
		return os.path.join(path, scrub(fname))
	
	_add_code(doc, _get_path(doc.name + '.js'), '__js')
	_add_code(doc, _get_path(doc.name + '.css'), "__css")
	_add_code(doc, _get_path(doc.name + '_list.js'), '__list_js')
	_add_code(doc, _get_path(doc.name + '_calendar.js'), '__calendar_js')
	_add_code(doc, _get_path(doc.name + '_map.js'), '__map_js')
	
	add_custom_script(doc)
	add_code_via_hook(doc, "doctype_js", "__js")
	
def _add_code(doc, path, fieldname):
	js = frappe.read_file(path)
	if js:
		doc.fields[fieldname] = (doc.fields.get(fieldname) or "") + "\n\n" + render_jinja(js)
		
def add_code_via_hook(doc, hook, fieldname):
	hook = "{}:{}".format(hook, doc.name)
	for app_name in frappe.get_installed_apps():
		for file in frappe.get_hooks(hook, app_name=app_name):
			path = frappe.get_app_path(app_name, *file.strip("/").split("/"))
			_add_code(doc, path, fieldname)
	
def add_custom_script(doc):
	"""embed all require files"""
	# custom script
	custom = frappe.db.get_value("Custom Script", {"dt": doc.name, 
		"script_type": "Client"}, "script") or ""
	
	doc.fields["__js"] = (doc.fields.get('__js') or '') + "\n\n".join(custom)
	
def render_jinja(content):
	if "{% include" in content:
		content = frappe.get_jenv().from_string(content).render()
	return content
	
def expand_selects(doclist):
	for d in filter(lambda d: d.fieldtype=='Select' \
		and (d.options or '').startswith('link:'), doclist):
		doctype = d.options.split("\n")[0][5:]
		d.link_doctype = doctype
		d.options = '\n'.join([''] + [o.name for o in frappe.db.sql("""select 
			name from `tab%s` where docstatus<2 order by name asc""" % doctype, as_dict=1)])

def add_print_formats(doclist):
	print_formats = frappe.db.sql("""select * FROM `tabPrint Format`
		WHERE doc_type=%s AND docstatus<2""", (doclist[0].name,), as_dict=1)
	for pf in print_formats:
		doclist.append(frappe.model.doc.Document('Print Format', fielddata=pf))

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
	for validator in frappe.db.sql("""select name from `tabDocType Validator` where
		for_doctype=%s""", (doctype,), as_dict=1):
		doclist.extend(frappe.get_doclist('DocType Validator', validator.name))
		
def add_search_fields(doclist):
	"""add search fields found in the doctypes indicated by link fields' options"""
	for lf in doclist.get({"fieldtype": "Link", "options":["!=", "[Select]"]}):
		if lf.options:
			search_fields = get(lf.options)[0].search_fields
			if search_fields:
				lf.search_fields = map(lambda sf: sf.strip(), search_fields.split(","))

def update_language(doclist):
	"""update language"""
	if frappe.local.lang != 'en':
		doclist[0].fields["__messages"] = frappe.get_lang_dict("doctype", doclist[0].name)

class DocTypeDocList(frappe.model.doclist.DocList):
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
			
	def has_field(self, fieldname):
		return fieldname in self.get_fieldnames()
		
	def get_fieldnames(self, filters=None):
		return map(lambda df: df.fieldname, self.get_docfields(filters))
		
	def get_docfields(self, filters=None):
		if not filters: filters = {}
		filters.update({"doctype": "DocField", "parent": self[0].name})
		return self.get(filters)
	
	def get_options(self, fieldname, parent=None, parentfield=None):
		return self.get_field(fieldname, parent, parentfield).options
		
	def get_label(self, fieldname, parent=None, parentfield=None):
		return self.get_field(fieldname, parent, parentfield).label
		
	def get_table_fields(self):
		return self.get({"doctype": "DocField", "fieldtype": "Table"})
		
	def get_parent_doclist(self):
		return frappe.doclist([self[0]] + self.get({"parent": self[0].name}))
		
	def get_restricted_fields(self, restricted_types):
		restricted_fields = self.get({
			"doctype":"DocField", 
			"fieldtype":"Link", 
			"parent": self[0].name, 
			"ignore_restrictions":("!=", 1), 
			"options":("in", restricted_types)
		})
		if self[0].name in restricted_types:
			restricted_fields.append(frappe._dict({"label":"Name", "fieldname":"name", "options": self[0].name}))
		return restricted_fields
		
	def get_permissions(self, user=None):
		user_roles = frappe.get_roles(user)
		return [p for p in self.get({"doctype": "DocPerm"})
				if cint(p.permlevel)==0 and (p.role=="All" or p.role in user_roles)]