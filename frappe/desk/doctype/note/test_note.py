# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors and Contributors
# See license.txt

import frappe
import unittest

test_records = frappe.get_test_records('Note')

class TestNote(unittest.TestCase):
	def insert_note(self):
		frappe.db.sql('delete from tabVersion')
		frappe.db.sql('delete from tabNote')
		frappe.db.sql('delete from `tabNote Seen By`')

		return frappe.get_doc(dict(doctype='Note', title='test note',
			content='test note content')).insert()

	def test_version(self):
		note = self.insert_note()
		note.title = 'test note 1'
		note.content = '1'
		note.save()

		version = frappe.get_doc('Version', dict(docname=note.name))
		data = version.get_data()

		self.assertTrue(('title', 'test note', 'test note 1'), data['changed'])
		self.assertTrue(('content', 'test note content', '1'), data['changed'])

	def test_rows(self):
		note = self.insert_note()

		# test add
		note.append('seen_by', {'user': 'Administrator'})
		note.save()

		version = frappe.get_doc('Version', dict(docname=note.name))
		data = version.get_data()

		self.assertEquals(len(data.get('added')), 1)
		self.assertEquals(len(data.get('removed')), 0)
		self.assertEquals(len(data.get('changed')), 0)

		for row in data.get('added'):
			self.assertEquals(row[0], 'seen_by')
			self.assertEquals(row[1]['user'], 'Administrator')

		# test row change
		note.seen_by[0].user = 'Guest'
		note.save()

		version = frappe.get_doc('Version', dict(docname=note.name))
		data = version.get_data()

		self.assertEquals(len(data.get('row_changed')), 1)
		for row in data.get('row_changed'):
			self.assertEquals(row[0], 'seen_by')
			self.assertEquals(row[1], 0)
			self.assertEquals(row[2], note.seen_by[0].name)
			self.assertEquals(row[3], [['user', 'Administrator', 'Guest']])

		# test remove
		note.seen_by = []
		note.save()

		version = frappe.get_doc('Version', dict(docname=note.name))
		data = version.get_data()

		self.assertEquals(len(data.get('removed')), 1)
		for row in data.get('removed'):
			self.assertEquals(row[0], 'seen_by')
			self.assertEquals(row[1]['user'], 'Guest')

		# self.assertTrue(('title', 'test note', 'test note 1'), data['changed'])
		# self.assertTrue(('content', 'test note content', '1'), data['changed'])
