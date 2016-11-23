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

	def test_insert(self):
		test_subject = 'testing global search'

		existing = frappe.db.get_value('Event', dict(subject=test_subject))
		if existing:
			frappe.delete_doc('Event', existing)

		global_search.reset()

		phrases = ['"The Sixth Extinction II: Amor Fati" is the second episode of the seventh season of the American science fiction television series The X-Files.',
			'After Mulder awakens from his coma, he realizes his duty to prevent alien colonization. ',
			"Carter explored themes of extraterrestrial involvement in ancient mass extinctions in this episode, the third in a trilogy focused on Mulder's severe reaction to an alien artifact."
		]

		events = []
		for text in phrases:
			events.append(frappe.get_doc(dict(
				doctype='Event',
				subject=text,
				starts_on=frappe.utils.now_datetime())).insert())

		frappe.db.commit()

		results = global_search.search('awakens')
		self.assertDictEqual(dict(doctype='Event', name=events[1].name), results[0])

		results = global_search.search('extraterrestrial')
		self.assertDictEqual(dict(doctype='Event', name=events[2].name), results[0])