# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import contextlib

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.desk.doctype.form_layout.form_layout import save_form_layout
from frappe.desk.doctype_editor.customize import get_customizations
from frappe.desk.doctype_editor.load import get_doctype_editor
from frappe.desk.doctype_editor.versions import base_version
from frappe.permissions import add_permission, update_permission_property
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

MANAGER = "editor-manager-47270@example.com"
CUSTOMIZER = "editor-customizer-47270@example.com"
READER = "editor-reader-47270@example.com"
CUSTOMIZER_ROLE = "Editor Customizer 47270"


@contextlib.contextmanager
def developer_mode(on: bool):
	original = frappe.conf.get("developer_mode")
	frappe.conf.developer_mode = 1 if on else 0
	try:
		yield
	finally:
		frappe.conf.developer_mode = original


def a_user(email: str, *roles: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			doctype="User",
			email=email,
			first_name="Editor",
			user_type="System User",
			roles=[{"role": role} for role in roles],
		).insert(ignore_permissions=True)
	return email


def a_customizer_role() -> str:
	"""A role that writes `Customize Form` and is not System Manager."""
	if not frappe.db.exists("Role", CUSTOMIZER_ROLE):
		frappe.get_doc(doctype="Role", role_name=CUSTOMIZER_ROLE).insert(ignore_permissions=True)
	add_permission("Customize Form", CUSTOMIZER_ROLE)
	update_permission_property("Customize Form", CUSTOMIZER_ROLE, 0, "write", 1)
	return CUSTOMIZER_ROLE


def a_tree(fieldname: str) -> str:
	return frappe.as_json(
		[{"name": "t", "sections": [{"name": "s", "columns": [{"name": "c", "fields": [fieldname]}]}]}]
	)


class TestDoctypeEditor(IntegrationTestCase):
	def setUp(self):
		self.manager = a_user(MANAGER, "System Manager")
		self.customizer = a_user(CUSTOMIZER, a_customizer_role())
		self.reader = a_user(READER)

	def tearDown(self):
		frappe.db.rollback()
		frappe.clear_cache(doctype="Customize Form")

	def open(self, user: str, doctype: str, mode: str | None = None) -> dict:
		with set_user(user):
			return get_doctype_editor(doctype, mode)

	def test_developer_mode_opens_a_standard_doctype_in_design(self):
		with developer_mode(True):
			editor = self.open(self.manager, "ToDo")
			self.assertEqual((editor["mode"], editor["modes"]), ("Design", ["Design", "Customize"]))
			self.assertEqual(self.open(self.manager, "ToDo", "Customize")["mode"], "Customize")

	def test_without_developer_mode_a_standard_doctype_opens_only_in_customize(self):
		with developer_mode(False):
			self.assertEqual(self.open(self.manager, "ToDo")["mode"], "Customize")
			with self.assertRaises(frappe.PermissionError):
				self.open(self.manager, "ToDo", "Design")

	def test_customize_needs_write_on_customize_form(self):
		with developer_mode(True):
			self.assertEqual(self.open(self.customizer, "ToDo")["modes"], ["Customize"])
			with self.assertRaises(frappe.PermissionError):
				self.open(self.customizer, "ToDo", "Design")
			with self.assertRaises(frappe.PermissionError):
				self.open(self.reader, "ToDo")

	def test_a_standard_single_opens_only_in_design(self):
		with developer_mode(True):
			self.assertEqual(self.open(self.manager, "System Settings")["modes"], ["Design"])
		with developer_mode(False), self.assertRaises(frappe.PermissionError):
			self.open(self.manager, "System Settings")

	def test_a_custom_doctype_opens_in_design_without_developer_mode(self):
		doctype = new_doctype(custom=1).insert().name
		with developer_mode(False):
			editor = self.open(self.manager, doctype)
			self.assertEqual((editor["mode"], editor["modes"]), ("Design", ["Design"]))
			with self.assertRaises(frappe.PermissionError):
				self.open(self.customizer, doctype, "Design")
			with self.assertRaises(frappe.PermissionError):
				self.open(self.customizer, doctype)

	def test_design_hides_site_custom_fields_and_counts_them(self):
		create_custom_field("ToDo", {"fieldname": "editor_47270", "label": "Editor", "fieldtype": "Data"})
		with developer_mode(True):
			editor = self.open(self.manager, "ToDo", "Design")
		fieldnames = {df["fieldname"] for df in editor["definition"]["fields"]}
		self.assertNotIn("editor_47270", fieldnames)
		self.assertGreaterEqual(editor["site_custom_fields"], 1)
		fallback = frappe.as_json(editor["layouts"]["Details"][0]["layout"])
		self.assertNotIn("editor_47270", fallback)

		customize = self.open(self.manager, "ToDo", "Customize")
		self.assertIn("editor_47270", {row["fieldname"] for row in customize["custom_fields"]})
		self.assertIn("editor_47270", frappe.as_json(customize["layouts"]["Details"][0]["layout"]))

	def test_customize_sends_lock_reasons_and_app_values(self):
		frappe.make_property_setter(
			{"doctype": "ToDo", "fieldname": "description", "property": "bold", "value": "1"},
			is_system_generated=False,
		)
		editor = self.open(self.customizer, "ToDo")
		self.assertIn("reqd", editor["locks"]["description"])
		self.assertIn("options", editor["locks"]["status"])
		self.assertNotIn("options", editor["locks"].get("sender", {}))
		self.assertEqual(
			editor["fieldtype_changes"]["description"], ["Code", "HTML Editor", "Signature", "Text"]
		)
		[setter] = [row for row in editor["property_setters"] if row["property"] == "bold"]
		self.assertEqual((setter["value"], setter["app_value"]), ("1", 0))

	def test_app_values_of_link_rows(self):
		[link] = frappe.get_doc("DocType", "Role Profile").links
		frappe.get_doc(
			doctype="Property Setter",
			doc_type="Role Profile",
			doctype_or_field="DocType Link",
			row_name=link.name,
			property="hidden",
			property_type="Check",
			value="1",
		).insert(ignore_permissions=True)
		[setter] = get_customizations(frappe.get_meta("Role Profile"))["property_setters"]
		self.assertEqual((setter["value"], setter["app_value"]), ("1", 0))

	def test_each_layout_type_names_its_source(self):
		with developer_mode(True):
			layouts = self.open(self.manager, "Note", "Design")["layouts"]
			self.assertEqual(
				{type: [layout["source"] for layout in rows] for type, rows in layouts.items()},
				{
					"Details": ["fallback"],
					"Side Panel": ["none"],
					"Quick Entry": ["fallback"],
					"New Record": ["same as Details"],
				},
			)
			with set_user(self.manager):
				save_form_layout("Note", "Details", a_tree("title"), title="Site")
			site, fallback = self.open(self.manager, "Note", "Design")["layouts"]["Details"]
		self.assertEqual((site["source"], site["title"]), ("site", "Site"))
		self.assertEqual(fallback["source"], "fallback")

	def test_a_single_lists_only_its_layout_types(self):
		with developer_mode(True):
			layouts = self.open(self.manager, "System Settings")["layouts"]
		self.assertEqual(list(layouts), ["Details", "Side Panel"])

	def test_counts_for_a_system_manager_who_is_not_administrator(self):
		frappe.get_doc(doctype="ToDo", description="editor 47270", priority="").insert()
		editor = self.open(self.manager, "ToDo", "Customize")
		self.assertEqual(editor["record_count"], frappe.db.count("ToDo"))
		self.assertEqual(
			editor["value_counts"]["description"],
			frappe.db.count("ToDo", {"description": ("is", "set")}),
		)
		self.assertEqual(
			editor["value_counts"]["priority"], frappe.db.count("ToDo", {"priority": ("is", "set")})
		)

	def test_counts_cover_only_the_records_the_user_reads(self):
		frappe.get_doc(doctype="ToDo", description="editor 47270 hidden").insert()
		with set_user(self.customizer):
			frappe.get_doc(doctype="ToDo", description="editor 47270 own").insert()
			readable = frappe.get_list("ToDo", pluck="description")
		editor = self.open(self.customizer, "ToDo", "Customize")
		self.assertEqual(editor["record_count"], len(readable))
		self.assertEqual(editor["value_counts"]["description"], len(readable))
		self.assertLess(editor["record_count"], frappe.db.count("ToDo"))

	def test_child_table_counts_add_up_the_parents_the_user_reads(self):
		with developer_mode(True):
			everything = self.open("Administrator", "Has Role", "Design")["record_count"]
			managed = self.open(self.manager, "Has Role", "Design")["record_count"]
		hidden = frappe.db.count("Has Role", {"parenttype": "User", "parent": "Administrator"})
		self.assertGreater(managed, 0)
		self.assertLessEqual(managed, everything - hidden)

	def test_a_child_table_names_the_parents_the_user_reads(self):
		with developer_mode(True):
			parents = self.open(self.manager, "Has Role", "Design")["parents"]
		self.assertIn("User", parents)
		self.assertNotIn("parents", self.open(self.manager, "ToDo"))

	def test_counts_of_masked_fields_stay_numbers(self):
		masked = [
			{"label": "Email", "fieldname": "email", "fieldtype": "Data", "options": "Email", "mask": 1},
			{"label": "Code", "fieldname": "code", "fieldtype": "Data", "mask": 1},
		]
		doctype = new_doctype(fields=masked).insert().name
		frappe.get_doc(doctype=doctype, email="editor-47270@example.com", code="x").insert()
		editor = self.open(self.manager, doctype)
		self.assertEqual(editor["value_counts"], {"email": 1, "code": 1})

	def test_counts_need_read_on_the_doctype_or_a_parent(self):
		editor = self.open(self.customizer, "Webhook", "Customize")
		self.assertEqual((editor["record_count"], editor["value_counts"]), (None, {}))
		with developer_mode(True):
			self.assertIsNotNone(self.open(self.manager, "Has Role", "Design")["record_count"])

	def test_the_load_sends_the_version_a_save_compares(self):
		with developer_mode(True):
			before = self.open(self.manager, "Note", "Design")["base_version"]
			self.assertEqual(before, base_version("Note"))
			with set_user(self.manager):
				save_form_layout("Note", "Details", a_tree("title"))
			self.assertNotEqual(self.open(self.manager, "Note", "Design")["base_version"], before)
