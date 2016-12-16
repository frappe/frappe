# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe

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

def reset():
	'''Deletes all data in __global_search'''
	frappe.db.sql('delete from __global_search')

def insert_test_events():
	phrases1 = ['"The Sixth Extinction II: Amor Fati" is the second episode of the seventh season of the American science fiction.','After Mulder awakens from his coma, he realizes his duty to prevent alien colonization. ',"Carter explored themes of extraterrestrial involvement in ancient mass extinctions in this episode, the third in a trilogy."]
	phrases2 = ['Hydrus is a small constellation in the deep southern sky. ','It was first depicted on a celestial atlas by Johann Bayer in his 1603 Uranometria. ','The French explorer and astronomer Nicolas Louis de Lacaille charted the brighter stars and gave their Bayer designations in 1756. ','Its name means "male water snake", as opposed to Hydra, a much larger constellation that represents a female water snake. ','It remains below the horizon for most Northern Hemisphere observers.',
	'The brightest star is the 2.8-magnitude Beta Hydri, also the closest reasonably bright star to the south celestial pole. ','Pulsating between magnitude 3.26 and 3.33, Gamma Hydri is a variable red giant some 60 times the diameter of our Sun. ','Lying near it is VW Hydri, one of the brightest dwarf novae in the heavens. ','Four star systems have been found to have exoplanets to date, most notably HD 10180, which could bear up to nine planetary companions.']
	phrases3 = ['Keyzer and de Houtman assigned 15 stars to the constellation in their Malay and Madagascan vocabulary, with a star that ','Gamma the chest and a number of stars that were later allocated to Tucana, Reticulum, Mensa and Horologium marking the body and tail. ','Lacaille charted and designated 20 stars with the Bayer designations Alpha through to Tau in 1756. ','Of these, he used the designations Eta, Pi and Tau twice each, for three sets of two stars close together, and omitted Omicron and Xi. ','He assigned Rho to a star that subsequent astronomers were unable to find.']
	phrases = phrases3
	for text in phrases:
		frappe.get_doc(dict(doctype='Event',subject=text,starts_on=frappe.utils.now_datetime())).insert()
	frappe.db.commit()

def insert_test_contacts():
	first_names = ["abc", "fghj", "cvbnm", "vgyui"]
	for text in first_names:
		frappe.get_doc(dict(doctype='Contact',first_name=text)).insert()
	frappe.db.commit()

def update_global_search(doc):
	'''Add values marked with `in_global_search` to `frappe.flags.update_global_search` from given doc
	:param doc: Document to be added to global search'''
	if frappe.flags.update_global_search==None:
		frappe.flags.update_global_search = []

	# frappe.msgprint("============>>>>>>>>doc.name")
	# frappe.msgprint(doc.name)

	content = []
	for field in doc.meta.fields:
		# subject, type etc in THAT event: EV00010
		if getattr(field, 'in_global_search', None):
			# subject is in global search
			if getattr(field, 'fieldtype', None) == "Table":
				# role(field) is of type Table
				child_doctype = getattr(field, 'options', None)
				# Event Role: doctype of role(field) table written in options
				for d in frappe.get_all(child_doctype):
					# For every bb54 of the Event Role doctype
				  	innerdoc = frappe.get_doc(child_doctype, d.name)
				  	if innerdoc.parent == doc.name:
				  		for field in innerdoc.meta.fields:
				  			if getattr(field, 'in_global_search', None):
				  				content.append(innerdoc.get(field.fieldname))
			else:
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
		delete 
			from __global_search
		where
			doctype = (%s)''', doctype, as_dict=True)

	for d in frappe.get_all(doctype):
		update_global_search(frappe.get_doc(doctype, d.name))
	sync_global_search()

def delete_for_document(doc):
	frappe.db.sql('''
		delete 
			from __global_search
		where
			name = (%s)''', doc.name, as_dict=True)

@frappe.whitelist()
def search(text, start=0, limit=20):
	'''Search for given text in __global_search

	:param text: phrase to be searched
	:param start: start results at, default 0
	:param limit: number of results to return, default 20'''
	print "Here's what I got:"
	text = "+" + text + "*"
	print text

	results = frappe.db.sql('''
		select
			doctype, name, content
		from
			__global_search
		where
			match(content) against ('{term}' IN NATURAL LANGUAGE MODE)
		limit {start}, {limit}'''.format(start=start, limit=limit, term=text), as_dict=True)
	print results
	return results

