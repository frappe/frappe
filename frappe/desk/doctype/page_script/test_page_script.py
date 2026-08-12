# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.page_script.page_script import get_page_scripts
from frappe.tests import IntegrationTestCase


def make_script(name, **kwargs):
	values = {
		"doctype": "Page Script",
		"__newname": name,
		"dt": "Note",
		"view": "Record",
		"script": "export default {}",
	}
	values.update(kwargs)
	return frappe.get_doc(values)


class TestPageScript(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_returns_enabled_scripts_in_creation_order(self):
		make_script("first-note-script").insert()
		make_script("second-note-script").insert()
		make_script("disabled-note-script", enabled=0).insert()

		names = [row["name"] for row in get_page_scripts("Note", "Record")["scripts"]]
		self.assertEqual(names, ["first-note-script", "second-note-script"])

	def test_scopes_to_the_doctype(self):
		make_script("note-script").insert()
		make_script("todo-script", dt="ToDo").insert()

		names = [row["name"] for row in get_page_scripts("ToDo", "Record")["scripts"]]
		self.assertEqual(names, ["todo-script"])

	def test_rejects_an_unknown_view(self):
		self.assertRaises(frappe.ValidationError, get_page_scripts, "Note", "List")

	def test_rejects_a_doctype_filter_posing_as_a_name(self):
		make_script("note-script").insert()
		self.assertRaises(frappe.FrappeTypeError, get_page_scripts, ["!=", ""], "Record")

	def test_reports_write_access_for_the_toast_gate(self):
		self.assertTrue(get_page_scripts("Note", "Record")["can_write"])
