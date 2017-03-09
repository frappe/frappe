# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe
from frappe.utils import cint

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
			unique (doctype, name))
			COLLATE=utf8mb4_unicode_ci
			ENGINE=MyISAM
			CHARACTER SET=utf8mb4''')

def reset():
	'''Deletes all data in __global_search'''
	frappe.db.sql('delete from __global_search')

def update_global_search(doc):
	'''Add values marked with `in_global_search` to
		`frappe.flags.update_global_search` from given doc
	:param doc: Document to be added to global search'''

	if cint(doc.meta.istable) == 1 and frappe.db.exists("DocType", doc.parenttype):
		d = frappe.get_doc(doc.parenttype, doc.parent)
		update_global_search(d)
		return

	if frappe.flags.update_global_search==None:
		frappe.flags.update_global_search = []

	content = []
	for field in doc.meta.get_global_search_fields():
		if doc.get(field.fieldname):
			if getattr(field, 'fieldtype', None) == "Table":

				# Get children
				for d in doc.get(field.fieldname):
				  	if d.parent == doc.name:
				  		for field in d.meta.get_global_search_fields():
				  			if d.get(field.fieldname):
				  				content.append(field.label + ": " + unicode(d.get(field.fieldname)))
			else:
				content.append(field.label + ": " + unicode(doc.get(field.fieldname)))

	if content:
		published = 0
		if hasattr(doc, 'is_website_published') and doc.meta.allow_guest_to_view:
			published = 1 if doc.is_website_published() else 0

		frappe.flags.update_global_search.append(
			dict(doctype=doc.doctype, name=doc.name, content='|||'.join(content or ''),
				published=published, title=doc.get_title(), route=doc.get('route')))

def sync_global_search():
	'''Add values from `frappe.flags.update_global_search` to __global_search.
		This is called internally at the end of the request.'''

	for value in frappe.flags.update_global_search:
		frappe.db.sql('''
			insert into __global_search
				(doctype, name, content, published, title, route)
			values
				(%(doctype)s, %(name)s, %(content)s, %(published)s, %(title)s, %(route)s)
			on duplicate key update
				content = %(content)s''', value)

	frappe.flags.update_global_search = []

def rebuild_for_doctype(doctype):
	'''Rebuild entries of doctype's documents in __global_search on change of
		searchable fields
	:param doctype: Doctype '''

	frappe.flags.update_global_search = []

	frappe.db.sql('''
			delete
				from __global_search
			where
				doctype = %s''', doctype, as_dict=True)

	for d in frappe.get_all(doctype):
		update_global_search(frappe.get_doc(doctype, d.name))
	sync_global_search()

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
def search(text, start=0, limit=20):
	'''Search for given text in __global_search
	:param text: phrase to be searched
	:param start: start results at, default 0
	:param limit: number of results to return, default 20
	:return: Array of result objects'''

	text = "+" + text + "*"
	results = frappe.db.sql('''
		select
			doctype, name, content
		from
			__global_search
		where
			match(content) against (%s IN BOOLEAN MODE)
		limit {start}, {limit}'''.format(start=start, limit=limit), text, as_dict=True)
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

@frappe.whitelist()
def get_search_doctypes(text):
	'''Search for all t
	:param text: phrase to be searched
	:return: Array of result objects'''

	text = "+" + text + "*"
	results = frappe.db.sql('''
		select
			doctype
		from
			__global_search
		where
			match(content) against (%s IN BOOLEAN MODE)
		group by
			doctype
		order by
			count(doctype) desc limit 0, 80''', text, as_dict=True)
	return results

@frappe.whitelist()
def search_in_doctype(doctype, text, start, limit):
	'''Search for given text in given doctype in __global_search
	:param doctype: doctype to be searched in
	:param text: phrase to be searched
	:param start: start results at, default 0
	:param limit: number of results to return, default 20
	:return: Array of result objects'''

	text = "+" + text + "*"
	results = frappe.db.sql('''
		select
			doctype, name, content
		from
			__global_search
		where
			doctype = %s AND
			match(content) against (%s IN BOOLEAN MODE)
		limit {start}, {limit}'''.format(start=start, limit=limit), (doctype, text), as_dict=True)

	return results
