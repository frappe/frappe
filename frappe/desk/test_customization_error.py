# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.customization_error import report_customization_error
from frappe.tests import IntegrationTestCase

PAYLOAD = {
	"source": "client-script:broken-todo",
	"tier": "client_script",
	"event": "load",
	"doctype": "ToDo",
	"message": "boom is not defined",
	"stack": "ReferenceError: boom is not defined\n    at load (client-script:broken-todo:1:1)",
	"record": "TODO-0001",
	"route": "/app/todo/TODO-0001",
}


class TestCustomizationError(IntegrationTestCase):
	def setUp(self):
		self.forget_reports()

	def tearDown(self):
		self.forget_reports()

	# Error Log is MyISAM on MariaDB, so the class rollback leaves these rows behind.
	def forget_reports(self):
		frappe.cache.delete_keys("customization_error:*")
		frappe.db.delete("Error Log", {"method": ("like", "%client-script:%")})

	def test_reader_writes_one_row_with_stack(self):
		with self.set_user("test@example.com"):
			name = report_customization_error(**PAYLOAD)

		row = frappe.get_doc("Error Log", name)
		self.assertEqual(row.method, "Client Script error on ToDo: client-script:broken-todo load")
		self.assertEqual(row.reference_doctype, "ToDo")
		self.assertEqual(row.reference_name, "TODO-0001")
		self.assertIn("boom is not defined", row.error)
		self.assertIn("at load (client-script:broken-todo:1:1)", row.error)
		self.assertIn("Route: /app/todo/TODO-0001", row.error)
		self.assertTrue(row.fingerprint)

	def test_same_failure_in_window_is_not_filed_again_by_the_same_user(self):
		with self.set_user("test@example.com"):
			first = report_customization_error(**PAYLOAD)
			repeat = report_customization_error(**PAYLOAD)
			other = report_customization_error(**{**PAYLOAD, "message": "boom2 is not defined"})

		self.assertTrue(first)
		self.assertIsNone(repeat)
		self.assertTrue(other)
		self.assertEqual(frappe.db.count("Error Log", {"method": ("like", "%broken-todo%")}), 2)

	def test_one_user_cannot_suppress_another_users_report(self):
		with self.set_user("test1@example.com"):
			report_customization_error(**PAYLOAD)
		with self.set_user("test@example.com"):
			name = report_customization_error(**PAYLOAD)

		self.assertTrue(name)
		self.assertEqual(frappe.db.count("Error Log", {"method": ("like", "%broken-todo%")}), 2)

	def test_unknown_doctype_leaves_the_link_empty(self):
		name = report_customization_error(**{**PAYLOAD, "doctype": "No Such DocType"})

		row = frappe.get_doc("Error Log", name)
		self.assertIsNone(row.reference_doctype)
		self.assertEqual(row.method, "Client Script error on No Such DocType: client-script:broken-todo load")

	def test_long_fields_are_cut(self):
		name = report_customization_error(**{**PAYLOAD, "message": "x" * 5000, "stack": "y" * 9000})

		row = frappe.get_doc("Error Log", name)
		self.assertNotIn("x" * 1001, row.error)
		self.assertNotIn("y" * 4001, row.error)

	def test_whitelist_admits_a_user_and_refuses_guest(self):
		with self.set_user("test@example.com"):
			frappe.is_whitelisted(report_customization_error)
		with self.set_user("Guest"):
			self.assertRaises(frappe.PermissionError, frappe.is_whitelisted, report_customization_error)

	def test_newlines_in_short_fields_do_not_reach_the_title(self):
		name = report_customization_error(**{**PAYLOAD, "source": "client-script:two\nlines"})

		row = frappe.get_doc("Error Log", name)
		self.assertEqual(row.method, "Client Script error on ToDo: client-script:two lines load")

	def test_unknown_tier_is_refused(self):
		self.assertRaises(frappe.ValidationError, report_customization_error, **{**PAYLOAD, "tier": "plugin"})
