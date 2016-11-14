# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe

def setup_table():
	'''Creates __global_seach table'''
	if not '__global_search' in frappe.db.get_tables():
		frappe.db.sql('''create table __global_search(
			doctype varchar(100),
			name varchar(140),
			content text,
			fulltext(content),
			unique (doctype, name))
			COLLATE=utf8mb4_unicode_ci
			ENGINE=MyISAM
			CHARACTER SET=utf8mb4''')

def reset():
	'''Deletes all data in __global_search'''
	frappe.db.sql('delete from __global_search')

def search(text, start=0, limit=20):
	'''Search for given text in __global_search

	:param text: phrase to be searched
	:param start: start results at, default 0
	:param limit: number of results to return, default 20'''

	return frappe.db.sql('''
		select
			doctype, name
		from
			__global_search
		where
			match(content) against (%s)
		limit {start}, {limit}'''.format(start=start, limit=limit),
			text, as_dict=True)

def update_global_search(doc):
	'''Add values marked with `in_global_search` to `frappe.flags.update_global_search` from given doc

	:param doc: Document to be added to global search'''
	if frappe.flags.update_global_search==None:
		frappe.flags.update_global_search = []

	content = []
	for field in doc.meta.fields:
		if getattr(field, 'in_global_search', None):
			content.append(doc.get(field.fieldname))

	if content:
		frappe.flags.update_global_search.append(
			dict(doctype=doc.doctype, name=doc.name, content=', '.join(content)))

def sync_global_search():
	'''Add values from `frappe.flags.update_global_search` to __global_search.
	This is called internally at the end of the request.'''
	if frappe.flags.update_global_search:
		for value in frappe.flags.update_global_search:
			frappe.db.sql('''
				insert into __global_search
					(doctype, name, content)
				values
					(%(doctype)s, %(name)s, %(content)s)
				on duplicate key update
					content = %(content)s''', value)