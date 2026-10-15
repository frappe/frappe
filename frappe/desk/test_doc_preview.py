# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doc_preview import get_preview
from frappe.tests import IntegrationTestCase


class TestDocPreview(IntegrationTestCase):
	def setUp(self):
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "doc preview test"}).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		self.todo.delete()

	def test_returns_doc_and_permlevels(self):
		preview = get_preview("ToDo", self.todo.name)

		self.assertEqual(preview["doc"]["name"], self.todo.name)
		self.assertIn(0, preview["permlevels"])

	def test_does_not_write_a_view_log(self):
		"""getdoc calls add_viewed; the preview must not."""
		before = frappe.db.count("View Log", {"reference_doctype": "ToDo", "reference_name": self.todo.name})
		get_preview("ToDo", self.todo.name)
		after = frappe.db.count("View Log", {"reference_doctype": "ToDo", "reference_name": self.todo.name})

		self.assertEqual(before, after)

	def test_checks_read_permission(self):
		user = frappe.get_doc(
			{"doctype": "User", "email": "doc-preview-noaccess@example.com", "first_name": "No Access"}
		)
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "User", user.name, force=True, ignore_permissions=True)

		frappe.set_user(user.name)
		with self.assertRaises(frappe.PermissionError):
			get_preview("ToDo", self.todo.name)
