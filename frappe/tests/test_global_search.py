# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe

from frappe.utils import global_search
import frappe.utils

class TestGlobalSearch(unittest.TestCase):
	def setUp(self):
		global_search.setup_table()
		self.assertTrue('__global_search' in frappe.db.get_tables())
		print "In setup"

		# doctype = "Event"
		# from frappe.custom.doctype.property_setter.property_setter import make_property_setter
		# make_property_setter(doctype, "subject", "in_global_search", 0, "Int")

		global_search.reset()

		self.insert_test_events()

		

		event_doctype = frappe.get_doc('DocType', 'Event')
		event_doctype.validate()
		event_doctype.sync_global_search()



	def insert_test_events(self):
		phrases = ['"The Sixth Extinction II: Amor Fati" is the second episode of the seventh season of the American science fiction.',
			'After Mulder awakens from his coma, he realizes his duty to prevent alien colonization. ',
			"Carter explored themes of extraterrestrial involvement in ancient mass extinctions in this episode, the third in a trilogy."
		]

		for text in phrases:
			frappe.get_doc(dict(
				doctype='Event',
				subject=text,
				starts_on=frappe.utils.now_datetime())).insert()

		frappe.db.commit()



	def test_search(self):
		search_table = frappe.db.sql('''select * from __global_search''', as_dict=True)

		print "SEARCH TABLE"
		print search_table

		phrases = ['"The Sixth Extinction II: Amor Fati" is the second episode of the seventh season of the American science fiction.',
			'After Mulder awakens from his coma, he realizes his duty to prevent alien colonization. ',
			"Carter explored themes of extraterrestrial involvement in ancient mass extinctions in this episode, the third in a trilogy."
		]

		events = []
		for text in phrases:
			events.append(frappe.get_doc('Event', dict(subject=text)))

		results = global_search.search('awakens')
		self.assertDictEqual(dict(doctype='Event', name=events[1].name), results[0])

		results = global_search.search('extraterrestrial')
		self.assertDictEqual(dict(doctype='Event', name=events[2].name), results[0])

	# def tearDown(self):
	# 	print "The property setter table before"
	# 	print frappe.db.sql('select * from `tabProperty Setter`')
	# 	frappe.db.sql('delete from `tabProperty Setter`')

	# 	frappe.clear_cache(doctype='Event')