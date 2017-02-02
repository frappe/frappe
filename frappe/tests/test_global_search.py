# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe

from frappe.utils import global_search
import frappe.utils

class TestGlobalSearch(unittest.TestCase):
	def setUp(self):
		global_search.setup_global_search_table()
		self.assertTrue('__global_search' in frappe.db.get_tables())
		doctype = "Event"
		global_search.reset()
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter
		make_property_setter(doctype, "subject", "in_global_search", 1, "Int")
		make_property_setter(doctype, "event_type", "in_global_search", 1, "Int")

	def insert_test_events(self):
		frappe.db.sql('delete from tabEvent')
		phrases = ['"The Sixth Extinction II: Amor Fati" is the second episode of the seventh season of the American science fiction.',
		'After Mulder awakens from his coma, he realizes his duty to prevent alien colonization. ',
		'Carter explored themes of extraterrestrial involvement in ancient mass extinctions in this episode, the third in a trilogy.']

		for text in phrases:
			frappe.get_doc(dict(
				doctype='Event',
				subject=text,
				repeat_on='Every Month',
				starts_on=frappe.utils.now_datetime())).insert()

		frappe.db.commit()

	def test_search(self):
		self.insert_test_events()
		results = global_search.search('awakens')
		self.assertTrue('After Mulder awakens from his coma, he realizes his duty to prevent alien colonization. ' in results[0].content)

		results = global_search.search('extraterrestrial')
		self.assertTrue('Carter explored themes of extraterrestrial involvement in ancient mass extinctions in this episode, the third in a trilogy.' in results[0].content)

	def test_update_doc(self):
		self.insert_test_events()
		test_subject = 'testing global search'
		event = frappe.get_doc('Event', frappe.get_all('Event')[0].name)
		event.subject = test_subject
		event.save()
		frappe.db.commit()

		results = global_search.search('testing global search')

		self.assertTrue('testing global search' in results[0].content)

	def test_update_fields(self):
		results = global_search.search('Every Month')
		self.assertEquals(len(results), 0)
		doctype = "Event"
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter
		make_property_setter(doctype, "repeat_on", "in_global_search", 1, "Int")
		global_search.rebuild_for_doctype(doctype)
		results = global_search.search('Every Month')
		self.assertEquals(len(results), 3)

	def test_delete_doc(self):
		self.insert_test_events()

		event_name = frappe.get_all('Event')[0].name
		event = frappe.get_doc('Event', event_name)
		test_subject = event.subject
		results = global_search.search(test_subject)
		self.assertEquals(len(results), 1)

		frappe.delete_doc('Event', event_name)

		results = global_search.search(test_subject)
		self.assertEquals(len(results), 0)

	def test_insert_child_table(self):
		frappe.db.sql('delete from tabEvent')
		phrases = ['"The Sixth Extinction II: Amor Fati" is the second episode of the seventh season of the American science fiction.',
		'After Mulder awakens from his coma, he realizes his duty to prevent alien colonization. ',
		'Carter explored themes of extraterrestrial involvement in ancient mass extinctions in this episode, the third in a trilogy.']

		for text in phrases:
			doc = frappe.get_doc({
				'doctype':'Event',
				'subject': text,
				'starts_on': frappe.utils.now_datetime()
			})
			doc.append('roles', dict(role='Student'))
			doc.insert()
		
		frappe.db.commit()
		results = global_search.search('Student')
		self.assertEquals(len(results), 3)

	def tearDown(self):
		frappe.db.sql('delete from `tabProperty Setter`')
		frappe.clear_cache(doctype='Event')