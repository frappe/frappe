# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.desk.doctype.form_layout.form_layout import get_form_layouts, save_form_layout
from frappe.desk.doctype.form_layout.test_form_layout import a_manager, make_layout
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

# Rows can only name an installed app, and CI sites have frappe alone; a read may name any app.
APP = "frappe"
OTHER_APP = "test_app_45899"


def a_tree(fieldname: str) -> str:
	return json.dumps([{"sections": [{"columns": [{"fields": [fieldname]}]}]}])


class TestFormLayoutApp(IntegrationTestCase):
	def setUp(self):
		frappe.db.delete("Form Layout", {"dt": "Note"})

	def tearDown(self):
		frappe.db.rollback()

	def read(self, app: str | None, type: str = "Details") -> dict:
		with set_user(a_manager()):
			return get_form_layouts("Note", type, app)

	def names(self, app: str | None, type: str = "Details") -> list:
		return [row["name"] for row in self.read(app, type)["layouts"]]

	def test_one_default_per_app(self):
		make_layout().insert()
		make_layout(app=APP).insert()
		self.assertRaises(frappe.ValidationError, make_layout(app=APP).insert)
		self.assertRaises(frappe.ValidationError, make_layout().insert)

	def test_a_blank_app_is_no_app(self):
		make_layout(app="").insert()
		self.assertRaises(frappe.ValidationError, make_layout().insert)

	def test_refuses_an_app_that_is_not_installed(self):
		self.assertRaises(frappe.ValidationError, make_layout(app=OTHER_APP).insert)
		self.assertEqual(make_layout(app=f" {APP} ").insert().app, APP)

	def test_rows_naming_the_app_replace_rows_naming_none(self):
		make_layout().insert()
		make_layout(condition="doc.public").insert()
		named = make_layout(app=APP).insert()
		self.assertEqual(self.names(APP), [named.name])

	def test_condition_picks_among_the_apps_rows(self):
		make_layout().insert()
		named_default = make_layout(app=APP).insert()
		named_public = make_layout(app=APP, condition="doc.public").insert()
		self.assertEqual(self.names(APP), [named_default.name, named_public.name])

	def test_the_apps_conditional_rows_drop_the_unnamed_default(self):
		make_layout().insert()
		named = make_layout(app=APP, condition="doc.public").insert()
		self.assertEqual(self.names(APP), [named.name])

	def test_an_app_with_no_rows_of_its_own_gets_the_unnamed_rows(self):
		everywhere = make_layout().insert()
		make_layout(app=APP).insert()
		self.assertEqual(self.names(OTHER_APP), [everywhere.name])

	def test_the_index_gets_only_unnamed_rows(self):
		everywhere = make_layout().insert()
		make_layout(app=APP).insert()
		self.assertEqual(self.names(None), [everywhere.name])

	def test_new_record_falls_back_to_the_apps_details_rows(self):
		make_layout().insert()
		named = make_layout(app=APP).insert()
		self.assertEqual(self.names(APP, "New Record"), [named.name])

	def test_new_record_rows_of_any_app_come_before_details_rows(self):
		everywhere = make_layout(type="New Record").insert()
		make_layout(app=APP).insert()
		self.assertEqual(self.names(APP, "New Record"), [everywhere.name])

	def test_the_dialog_flag_reads_the_apps_rows(self):
		make_layout(type="Quick Entry", app=APP, layout=a_tree("title")).insert()
		self.assertTrue(self.read(APP, "Quick Entry")["dialog"])
		self.assertEqual(self.read(None, "Quick Entry")["layouts"], [])

	def test_save_finds_the_default_of_its_app(self):
		with set_user(a_manager()):
			everywhere = save_form_layout("Note", "Details", a_tree("title"))
			named = save_form_layout("Note", "Details", a_tree("content"), app=APP)
			self.assertNotEqual(everywhere, named)
			self.assertEqual(save_form_layout("Note", "Details", a_tree("public"), app=APP), named)
			self.assertEqual(save_form_layout("Note", "Details", a_tree("public")), everywhere)
		self.assertEqual(frappe.db.get_value("Form Layout", named, "app"), APP)

	def test_save_refuses_a_row_of_another_app(self):
		named = make_layout(app=APP).insert()
		with set_user(a_manager()), self.assertRaises(frappe.ValidationError):
			save_form_layout("Note", "Details", a_tree("title"), name=str(named.name))
		self.assertEqual(frappe.db.get_value("Form Layout", named.name, "app"), APP)
