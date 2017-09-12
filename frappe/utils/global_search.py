# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe
import re
from frappe.utils import cint, strip_html_tags
from frappe.model.base_document import get_controller
from six import text_type

def setup_global_search_table():
	'''Creates __global_seach table'''
	if not '__global_search' in frappe.db.get_tables():
		frappe.db.sql('''create table __global_search(
			doctype varchar(100),
			name varchar(140),
			title varchar(140),
			content text,
			fulltext(content),
			route varchar(140),
			published int(1) not null default 0,
			unique `doctype_name` (doctype, name))
			COLLATE=utf8mb4_unicode_ci
			ENGINE=MyISAM
			CHARACTER SET=utf8mb4''')

def reset():
	'''Deletes all data in __global_search'''
	frappe.db.sql('delete from __global_search')

def get_doctypes_with_global_search(with_child_tables=True):
	'''Return doctypes with global search fields'''
	def _get():
		global_search_doctypes = []
		filters = {}
		if not with_child_tables:
			filters = {"istable": ["!=", 1], "issingle": ["!=", 1]}
		for d in frappe.get_all('DocType', fields=['name', 'module'], filters=filters):
			meta = frappe.get_meta(d.name)
			if len(meta.get_global_search_fields()) > 0:
				global_search_doctypes.append(d)

		installed_apps = frappe.get_installed_apps()

		doctypes = [d.name for d in global_search_doctypes
			if frappe.local.module_app[frappe.scrub(d.module)] in installed_apps]
		return doctypes

	return frappe.cache().get_value('doctypes_with_global_search', _get)

def rebuild_for_doctype(doctype):
	'''Rebuild entries of doctype's documents in __global_search on change of
		searchable fields
	:param doctype: Doctype '''

	def _get_filters():
		filters = frappe._dict({ "docstatus": ["!=", 2] })
		if meta.has_field("enabled"):
			filters.enabled = 1
		if meta.has_field("disabled"):
			filters.disabled = 0

		return filters

	meta = frappe.get_meta(doctype)
	if cint(meta.istable) == 1:
		parent_doctypes = frappe.get_all("DocField", fields="parent", filters={
			"fieldtype": "Table",
			"options": doctype
		})
		for p in parent_doctypes:
			rebuild_for_doctype(p.parent)

		return

	# Delete records
	delete_global_search_records_for_doctype(doctype)

	parent_search_fields = meta.get_global_search_fields()
	fieldnames = get_selected_fields(meta, parent_search_fields)

	# Get all records from parent doctype table
	all_records = frappe.get_all(doctype, fields=fieldnames, filters=_get_filters())

	# Children data
	all_children, child_search_fields = get_children_data(doctype, meta)
	all_contents = []

	for doc in all_records:
		content = []
		for field in parent_search_fields:
			value = doc.get(field.fieldname)
			if value:
				content.append(get_formatted_value(value, field))

		# get children data
		for child_doctype, records in all_children.get(doc.name, {}).items():
			for field in child_search_fields.get(child_doctype):
				for r in records:
					if r.get(field.fieldname):
						content.append(get_formatted_value(r.get(field.fieldname), field))

		if content:
			# if doctype published in website, push title, route etc.
			published = 0
			title, route = "", ""
			try:
				if hasattr(get_controller(doctype), "is_website_published") and meta.allow_guest_to_view:
					d = frappe.get_doc(doctype, doc.name)
					published = 1 if d.is_website_published() else 0
					title = d.get_title()
					route = d.get("route")
			except ImportError:
				# some doctypes has been deleted via future patch, hence controller does not exists
				pass

			all_contents.append({
				"doctype": frappe.db.escape(doctype),
				"name": frappe.db.escape(doc.name),
				"content": frappe.db.escape(' ||| '.join(content or '')),
				"published": published,
				"title": frappe.db.escape(title or ''),
				"route": frappe.db.escape(route or '')
			})
	if all_contents:
		insert_values_for_multiple_docs(all_contents)

def delete_global_search_records_for_doctype(doctype):
	frappe.db.sql('''
		delete
			from __global_search
		where
			doctype = %s''', doctype, as_dict=True)

def get_selected_fields(meta, global_search_fields):
	fieldnames = [df.fieldname for df in global_search_fields]
	if meta.istable==1:
		fieldnames.append("parent")
	elif "name" not in fieldnames:
		fieldnames.append("name")

	if meta.has_field("is_website_published"):
		fieldnames.append("is_website_published")

	return fieldnames

def get_children_data(doctype, meta):
	"""
		Get all records from all the child tables of a doctype

		all_children = {
			"parent1": {
				"child_doctype1": [
					{
						"field1": val1,
						"field2": val2
					}
				]
			}
		}

	"""
	all_children = frappe._dict()
	child_search_fields = frappe._dict()

	for child in meta.get_table_fields():
		child_meta = frappe.get_meta(child.options)
		search_fields = child_meta.get_global_search_fields()
		if search_fields:
			child_search_fields.setdefault(child.options, search_fields)
			child_fieldnames = get_selected_fields(child_meta, search_fields)
			child_records = frappe.get_all(child.options, fields=child_fieldnames, filters={
				"docstatus": ["!=", 1],
				"parenttype": doctype
			})

			for record in child_records:
				all_children.setdefault(record.parent, frappe._dict())\
					.setdefault(child.options, []).append(record)

	return all_children, child_search_fields

def insert_values_for_multiple_docs(all_contents):
	values = []
	for content in all_contents:
		values.append("( '{doctype}', '{name}', '{content}', '{published}', '{title}', '{route}')"
			.format(**content))

	batch_size = 50000
	for i in range(0, len(values), batch_size):
		batch_values = values[i:i + batch_size]
		# ignoring duplicate keys for doctype_name
		frappe.db.sql('''
			insert ignore into __global_search
				(doctype, name, content, published, title, route)
			values
				{0}
			'''.format(", ".join(batch_values)))


def update_global_search(doc):
	'''Add values marked with `in_global_search` to
		`frappe.flags.update_global_search` from given doc
	:param doc: Document to be added to global search'''

	if doc.docstatus > 1 or (doc.meta.has_field("enabled") and not doc.get("enabled")) \
		or doc.get("disabled"):
			return

	if frappe.flags.update_global_search==None:
		frappe.flags.update_global_search = []

	content = []
	for field in doc.meta.get_global_search_fields():
		if doc.get(field.fieldname) and field.fieldtype != "Table":
			content.append(get_formatted_value(doc.get(field.fieldname), field))

	# Get children
	for child in doc.meta.get_table_fields():
		for d in doc.get(child.fieldname):
			if d.parent == doc.name:
				for field in d.meta.get_global_search_fields():
					if d.get(field.fieldname):
						content.append(get_formatted_value(d.get(field.fieldname), field))

	if content:
		published = 0
		if hasattr(doc, 'is_website_published') and doc.meta.allow_guest_to_view:
			published = 1 if doc.is_website_published() else 0

		frappe.flags.update_global_search.append(
			dict(doctype=doc.doctype, name=doc.name, content=' ||| '.join(content or ''),
				published=published, title=doc.get_title(), route=doc.get('route')))

def get_formatted_value(value, field):
	'''Prepare field from raw data'''

	from six.moves.html_parser import HTMLParser

	if(getattr(field, 'fieldtype', None) in ["Text", "Text Editor"]):
		h = HTMLParser()
		value = h.unescape(value)
		value = (re.subn(r'<[\s]*(script|style).*?</\1>(?s)', '', text_type(value))[0])
		value = ' '.join(value.split())
	return field.label + " : " + strip_html_tags(text_type(value))

def sync_global_search(flags=None):
	'''Add values from `flags` (frappe.flags.update_global_search) to __global_search.
		This is called internally at the end of the request.'''

	if not flags:
		flags = frappe.flags.update_global_search

	# Can pass flags manually as frappe.flags.update_global_search isn't reliable at a later time,
	# when syncing is enqueued
	for value in flags:
		frappe.db.sql('''
			insert into __global_search
				(doctype, name, content, published, title, route)
			values
				(%(doctype)s, %(name)s, %(content)s, %(published)s, %(title)s, %(route)s)
			on duplicate key update
				content = %(content)s''', value)

	frappe.flags.update_global_search = []

def delete_for_document(doc):
	'''Delete the __global_search entry of a document that has
		been deleted
		:param doc: Deleted document'''

	frappe.db.sql('''
		delete
			from __global_search
		where
			doctype = %s and
			name = %s''', (doc.doctype, doc.name), as_dict=True)

@frappe.whitelist()
def search(text, start=0, limit=20, doctype=""):
	'''Search for given text in __global_search
	:param text: phrase to be searched
	:param start: start results at, default 0
	:param limit: number of results to return, default 20
	:return: Array of result objects'''

	text = "+" + text + "*"
	if not doctype:
		results = frappe.db.sql('''
			select
				doctype, name, content
			from
				__global_search
			where
				match(content) against (%s IN BOOLEAN MODE)
			limit {start}, {limit}'''.format(start=start, limit=limit), text+"*", as_dict=True)
	else:
		results = frappe.db.sql('''
			select
				doctype, name, content
			from
				__global_search
			where
				doctype = %s AND
				match(content) against (%s IN BOOLEAN MODE)
			limit {start}, {limit}'''.format(start=start, limit=limit), (doctype, text), as_dict=True)

	for r in results:
		try:
			if frappe.get_meta(r.doctype).image_field:
				r.image = frappe.db.get_value(r.doctype, r.name, frappe.get_meta(r.doctype).image_field)
		except Exception:
			frappe.clear_messages()

	return results

@frappe.whitelist(allow_guest=True)
def web_search(text, start=0, limit=20):
	'''Search for given text in __global_search where published = 1
	:param text: phrase to be searched
	:param start: start results at, default 0
	:param limit: number of results to return, default 20
	:return: Array of result objects'''

	text = "+" + text + "*"
	results = frappe.db.sql('''
		select
			doctype, name, content, title, route
		from
			__global_search
		where
			published = 1 and
			match(content) against (%s IN BOOLEAN MODE)
		limit {start}, {limit}'''.format(start=start, limit=limit),
		text, as_dict=True)
	return results
