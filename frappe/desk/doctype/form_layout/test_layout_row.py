# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.desk.doctype.form_layout.form_layout import source_fingerprint, write_layout_row
from frappe.desk.doctype.form_layout.test_app_layout import a_tree
from frappe.desk.doctype.form_layout.test_form_layout import a_manager
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user


class TestLayoutRowWriter(IntegrationTestCase):
	def setUp(self):
		frappe.db.delete("Form Layout", {"dt": ("in", ("Note", "Has Role", "System Settings"))})
		self.enterContext(set_user(a_manager()))

	def tearDown(self):
		frappe.db.rollback()

	def write(self, doc=None, **values):
		return write_layout_row(doc or frappe.new_doc("Form Layout"), **values)

	def test_a_new_row_gets_its_values_and_the_source_fingerprint(self):
		row = self.write(dt="Note", type="Details", layout=json.dumps(a_tree("content")), title="Short")
		self.assertEqual((row.dt, row.type, row.title, row.app), ("Note", "Details", "Short", None))
		self.assertEqual(row.fingerprint, source_fingerprint("Note", "Details"))
		self.assertIn("title", json.loads(row.omitted))
		self.assertNotIn("content", json.loads(row.omitted))

	def test_a_value_the_caller_leaves_out_is_kept(self):
		row = self.write(
			dt="Note", type="Quick Entry", layout=json.dumps(a_tree("title")), app="frappe", title="Mine"
		)
		row = self.write(frappe.get_doc("Form Layout", row.name), layout=json.dumps(a_tree("content")))
		self.assertEqual((row.app, row.title, row.type), ("frappe", "Mine", "Quick Entry"))

	def test_a_layout_type_the_doctype_cannot_have_is_refused(self):
		for dt, type in (("Has Role", "Quick Entry"), ("System Settings", "New Record")):
			with self.assertRaises(frappe.ValidationError):
				self.write(dt=dt, type=type, layout="[]")
		self.assertFalse(frappe.db.exists("Form Layout", {"dt": ("in", ("Has Role", "System Settings"))}))

	def test_an_unknown_type_or_a_non_string_doctype_is_refused(self):
		for dt, type in (("Note", "Sidebar"), (["Note"], "Details")):
			with self.assertRaises(frappe.ValidationError):
				self.write(dt=dt, type=type, layout="[]")
