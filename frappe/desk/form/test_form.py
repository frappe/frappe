# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.form.linked_with import get_linked_docs, get_linked_doctypes
from frappe.desk.form.utils import _sort_field_fallback, get_next
from frappe.tests import IntegrationTestCase


class TestForm(IntegrationTestCase):
	def test_linked_with(self):
		results = get_linked_docs("Role", "System Manager", linkinfo=get_linked_doctypes("Role"))
		self.assertTrue("User" in results)
		self.assertTrue("DocType" in results)

	def test_sort_field_fallback(self):
		self.assertIsNone(_sort_field_fallback("Note", "name"))
		self.assertIsNone(_sort_field_fallback("Note", "creation"))
		self.assertIsNone(_sort_field_fallback("Note", "public"))
		self.assertEqual(_sort_field_fallback("Note", "expire_notification_on"), "0001-01-01")
		self.assertEqual(_sort_field_fallback("Event Notifications", "time"), "00:00:00")
		self.assertEqual(_sort_field_fallback("Note", "title"), "")
		self.assertEqual(_sort_field_fallback("Note", "nonexistent_field_xyz"), "")

	def test_get_next_with_null_sort_field(self):
		notes = []
		for i, expire in enumerate([None, "2099-01-01", None]):
			note = frappe.get_doc(
				{
					"doctype": "Note",
					"title": f"test_navigate_null_{frappe.generate_hash(length=8)}_{i}",
					"expire_notification_on": expire,
				}
			).insert(ignore_permissions=True)
			notes.append(note.name)

		try:
			filters = {"name": ["in", notes]}

			next_name = get_next(
				"Note",
				notes[0],
				prev=0,
				sort_field="expire_notification_on",
				sort_order="asc",
				filters=filters,
			)
			self.assertIsNotNone(next_name)
			self.assertIn(next_name, notes)

			prev_name = get_next(
				"Note",
				notes[1],
				prev=1,
				sort_field="expire_notification_on",
				sort_order="asc",
				filters=filters,
			)
			self.assertIsNotNone(prev_name)
			self.assertIn(prev_name, [notes[0], notes[2]])
		finally:
			for name in notes:
				frappe.delete_doc("Note", name, force=1, ignore_permissions=True)
