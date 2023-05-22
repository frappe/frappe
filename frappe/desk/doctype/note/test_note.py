# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests.utils import FrappeTestCase

test_records = frappe.get_test_records("Note")


class TestNote(FrappeTestCase):
	def insert_note(self):
		frappe.db.delete("Version")
		frappe.db.delete("Note")
		frappe.db.delete("Note Seen By")

		return frappe.get_doc(
			dict(doctype="Note", title="test note", content="test note content")
		).insert()

	def test_version(self):
		note = self.insert_note()
		note.title = "test note 1"
		note.content = "1"
		note.save(ignore_version=False)

		version = frappe.get_doc("Version", dict(docname=note.name))
		data = version.get_data()

		self.assertTrue(("title", "test note", "test note 1"), data["changed"])
		self.assertTrue(("content", "test note content", "1"), data["changed"])

	def test_rows(self):
		note = self.insert_note()

		# test add
		note.append("seen_by", {"user": "Administrator"})
		note.save(ignore_version=False)

		version = frappe.get_doc("Version", dict(docname=note.name))
		data = version.get_data()

		self.assertEqual(len(data.get("added")), 1)
		self.assertEqual(len(data.get("removed")), 0)
		self.assertEqual(len(data.get("changed")), 0)

		for row in data.get("added"):
			self.assertEqual(row[0], "seen_by")
			self.assertEqual(row[1]["user"], "Administrator")

		# test row change
		note.seen_by[0].user = "Guest"
		note.save(ignore_version=False)

		version = frappe.get_doc("Version", dict(docname=note.name))
		data = version.get_data()

		self.assertEqual(len(data.get("row_changed")), 1)
		for row in data.get("row_changed"):
			self.assertEqual(row[0], "seen_by")
			self.assertEqual(row[1], 0)
			self.assertEqual(row[2], note.seen_by[0].name)
			self.assertEqual(row[3], [["user", "Administrator", "Guest"]])

		# test remove
		note.seen_by = []
		note.save(ignore_version=False)

		version = frappe.get_doc("Version", dict(docname=note.name))
		data = version.get_data()

		self.assertEqual(len(data.get("removed")), 1)
		for row in data.get("removed"):
			self.assertEqual(row[0], "seen_by")
			self.assertEqual(row[1]["user"], "Guest")

		# self.assertTrue(('title', 'test note', 'test note 1'), data['changed'])
		# self.assertTrue(('content', 'test note content', '1'), data['changed'])
