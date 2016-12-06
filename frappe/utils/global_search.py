# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe


def reset():
	'''Deletes all data in __global_search'''
	frappe.db.sql('delete from __global_search')

def insert_test_events():
	phrases = ['"The Sixth Extinction II: Amor Fati" is the second episode of the seventh season of the American science fiction.','After Mulder awakens from his coma, he realizes his duty to prevent alien colonization. ',"Carter explored themes of extraterrestrial involvement in ancient mass extinctions in this episode, the third in a trilogy."]

	for text in phrases:
		frappe.get_doc(dict(doctype='Event',subject=text,starts_on=frappe.utils.now_datetime())).insert()

	frappe.db.commit()


def update_global_search(doc):
	'''Add values marked with `in_global_search` to `frappe.flags.update_global_search` from given doc

	:param doc: Document to be added to global search'''
	if frappe.flags.update_global_search==None:
		frappe.flags.update_global_search = []

	content = []
	for field in doc.meta.fields:
		if getattr(field, 'in_global_search', None):
			print "getattr:"
			print getattr(field, 'in_global_search', None)
			content.append(doc.get(field.fieldname))

	if content:
		frappe.flags.update_global_search.append(
			dict(doctype=doc.doctype, name=doc.name, content=', '.join(content)))
	print "FLAGS:"
	print frappe.flags.update_global_search

def sync_global_search():
	'''Add values from `frappe.flags.update_global_search` to __global_search.
	This is called internally at the end of the request.'''
	if frappe.flags.update_global_search:
		print "in SGS if"
		for value in frappe.flags.update_global_search:
			frappe.db.sql('''
				insert into __global_search
					(doctype, name, content)
				values
					(%(doctype)s, %(name)s, %(content)s)
				on duplicate key update
					content = %(content)s''', value)
	print "In SGS"

def rebuild_for_doctype(doctype):
	frappe.db.sql('''
		delete from __global_search
		where
			doctype = (%s)''', doctype, as_dict=True)

	for d in frappe.get_all(doctype):
		update_global_search(frappe.get_doc(doctype, d.name))
	sync_global_search()

@frappe.whitelist()
def setup_table():
	'''Creates __global_seach table'''
	print "creating table"
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
		print "Table created"
	print "Table not created"
	reset()
	# insert_test_events()
	# event_doctype = frappe.get_doc('DocType', 'Event')
	# event_doctype.validate()
	# event_doctype.sync_global_search()

@frappe.whitelist()
def search(text, start=0, limit=20):
	'''Search for given text in __global_search

	:param text: phrase to be searched
	:param start: start results at, default 0
	:param limit: number of results to return, default 20'''
	print "Here's what I got:"

	results = frappe.db.sql('''
		select
			doctype, name, content
		from
			__global_search
		where
			match(content) against ('{term}')
		limit {start}, {limit}'''.format(start=start, limit=limit, term=text), as_dict=True)
	print results
	return results

