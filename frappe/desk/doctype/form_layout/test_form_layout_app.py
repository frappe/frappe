# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.desk.doctype.form_layout.form_layout import get_form_layouts, save_form_layout
from frappe.desk.doctype.form_layout.test_form_layout import a_manager, make_layout
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user


def a_tree(fieldname: str) -> str:
	return json.dumps([{"sections": [{"columns": [{"fields": [fieldname]}]}]}])


class TestFormLayoutApp(IntegrationTestCase):
	def setUp(self):
		frappe.db.delete("Form Layout", {"dt": "Note"})

	def tearDown(self):
		frappe.db.rollback()

	def names(self, app: str | None, type: str = "Details") -> list:
		with set_user(a_manager()):
			return [row["name"] for row in get_form_layouts("Note", type, app)["layouts"]]

	def test_one_default_per_app(self):
		make_layout().insert()
		make_layout(app="crm").insert()
		make_layout(app="helpdesk").insert()
		self.assertRaises(frappe.ValidationError, make_layout(app="crm").insert)
		self.assertRaises(frappe.ValidationError, make_layout().insert)

	def test_rows_naming_the_app_replace_rows_naming_none(self):
		make_layout().insert()
		make_layout(condition="doc.public").insert()
		crm = make_layout(app="crm").insert()
		self.assertEqual(self.names("crm"), [crm.name])

	def test_condition_picks_among_the_apps_rows(self):
		make_layout().insert()
		crm_default = make_layout(app="crm").insert()
		crm_public = make_layout(app="crm", condition="doc.public").insert()
		self.assertEqual(self.names("crm"), [crm_default.name, crm_public.name])

	def test_an_app_with_no_rows_of_its_own_gets_the_unnamed_rows(self):
		everywhere = make_layout().insert()
		make_layout(app="crm").insert()
		self.assertEqual(self.names("frappe"), [everywhere.name])

	def test_the_index_gets_only_unnamed_rows(self):
		everywhere = make_layout().insert()
		make_layout(app="crm").insert()
		self.assertEqual(self.names(None), [everywhere.name])
		make_layout(app="frappe").insert()
		self.assertEqual(self.names(None), [everywhere.name])

	def test_new_record_falls_back_to_the_apps_details_rows(self):
		make_layout().insert()
		crm = make_layout(app="crm").insert()
		self.assertEqual(self.names("crm", "New Record"), [crm.name])

	def test_save_finds_the_default_of_its_app(self):
		with set_user(a_manager()):
			everywhere = save_form_layout("Note", "Details", a_tree("title"))
			crm = save_form_layout("Note", "Details", a_tree("content"), app="crm")
			self.assertNotEqual(everywhere, crm)
			self.assertEqual(save_form_layout("Note", "Details", a_tree("public"), app="crm"), crm)
			self.assertEqual(save_form_layout("Note", "Details", a_tree("public")), everywhere)
		self.assertEqual(frappe.db.get_value("Form Layout", crm, "app"), "crm")

	def test_save_refuses_a_row_of_another_app(self):
		crm = make_layout(app="crm").insert()
		with set_user(a_manager()), self.assertRaises(frappe.ValidationError):
			save_form_layout("Note", "Details", a_tree("title"), name=str(crm.name))
		self.assertEqual(frappe.db.get_value("Form Layout", crm.name, "app"), "crm")
