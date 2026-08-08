# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.custom import hide_customizations, unhide_customizations
from frappe.model.meta import is_field_hidden_by_app
from frappe.tests import IntegrationTestCase


class TestHideCustomizations(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.target = "ToDo"

	def test_hide_and_unhide_a_custom_field(self):
		fieldname = self.new_custom_field()
		customizations = {"Custom Field": [{"dt": self.target, "fieldname": fieldname}]}

		hide_customizations(customizations)
		self.assertEqual(frappe.db.get_value("Custom Field", {"fieldname": fieldname}, "is_app_disabled"), 1)

		unhide_customizations(customizations)
		self.assertEqual(frappe.db.get_value("Custom Field", {"fieldname": fieldname}, "is_app_disabled"), 0)

	def test_hide_and_unhide_a_property_setter(self):
		name = self.new_property_setter()
		customizations = {"Property Setter": [{"doc_type": self.target, "name": name}]}

		hide_customizations(customizations)
		self.assertEqual(frappe.db.get_value("Property Setter", name, "is_app_disabled"), 1)

		unhide_customizations(customizations)
		self.assertEqual(frappe.db.get_value("Property Setter", name, "is_app_disabled"), 0)

	def test_hide_and_unhide_a_custom_docperm(self):
		name = self.new_custom_docperm()
		customizations = {"Custom DocPerm": [{"parent": self.target, "name": name}]}

		hide_customizations(customizations)
		self.assertEqual(frappe.db.get_value("Custom DocPerm", name, "is_app_disabled"), 1)

		unhide_customizations(customizations)
		self.assertEqual(frappe.db.get_value("Custom DocPerm", name, "is_app_disabled"), 0)

	def test_rejects_a_doctype_that_is_not_a_customization(self):
		with self.assertRaises(frappe.ValidationError):
			hide_customizations({"ToDo": [{"dt": self.target}]})

	def test_rejects_a_filter_without_a_doctype_name(self):
		"""Without one doctype name the update would reach the rows of every other doctype."""
		fieldname = self.new_custom_field()

		with self.assertRaises(frappe.ValidationError):
			hide_customizations({"Custom Field": [{"fieldname": fieldname}]})

		with self.assertRaises(frappe.ValidationError):
			hide_customizations({"Custom Field": [{"dt": ["like", "%"], "fieldname": fieldname}]})

		self.assertEqual(frappe.db.get_value("Custom Field", {"fieldname": fieldname}, "is_app_disabled"), 0)

	def new_custom_field(self) -> str:
		"""`in_create_custom_fields` skips the schema sync, whose DDL would commit the row."""
		fieldname = f"custom_{frappe.generate_hash(length=8)}"
		frappe.flags.in_create_custom_fields = True
		try:
			frappe.get_doc(
				doctype="Custom Field", dt=self.target, fieldname=fieldname, fieldtype="Data"
			).insert()
		finally:
			frappe.flags.in_create_custom_fields = False
		return fieldname

	def new_property_setter(self) -> str:
		property_setter = frappe.get_doc(
			doctype="Property Setter",
			doctype_or_field="DocType",
			doc_type=self.target,
			property="max_attachments",
			value="2",
			property_type="Int",
		)
		property_setter.flags.validate_fields_for_doctype = False
		return property_setter.insert().name

	def new_custom_docperm(self) -> str:
		role = frappe.get_doc(
			doctype="Role", role_name=f"zzz Test Role {frappe.generate_hash(length=6)}"
		).insert()
		return (
			frappe.get_doc(doctype="Custom DocPerm", parent=self.target, role=role.name, read=1, permlevel=0)
			.insert()
			.name
		)


class TestFieldHiddenByApp(IntegrationTestCase):
	def test_field_flagged_by_its_own_app_is_hidden(self):
		self.assertTrue(is_field_hidden_by_app(frappe._dict(is_app_disabled=1)))
		self.assertFalse(is_field_hidden_by_app(frappe._dict(is_app_disabled=0)))

	def test_field_of_a_disabled_module_is_hidden(self):
		with patch("frappe.model.meta.is_module_disabled", side_effect=lambda module: module == "Core"):
			self.assertTrue(is_field_hidden_by_app(frappe._dict(module="Core")))
			self.assertFalse(is_field_hidden_by_app(frappe._dict(module="Desk")))

	def test_link_field_pointing_at_a_disabled_doctype_is_hidden(self):
		"""A link to a concealed doctype cannot work, whichever app declared the field."""
		with patch("frappe.app_state.get_disabled_doctypes", return_value={"ToDo"}):
			for fieldtype in ("Link", "Table", "Table MultiSelect"):
				with self.subTest(fieldtype=fieldtype):
					self.assertTrue(is_field_hidden_by_app(frappe._dict(fieldtype=fieldtype, options="ToDo")))

			self.assertFalse(is_field_hidden_by_app(frappe._dict(fieldtype="Link", options="Note")))
			self.assertFalse(is_field_hidden_by_app(frappe._dict(fieldtype="Data", options="ToDo")))

	def test_flagged_field_reappears_during_maintenance(self):
		frappe.flags.in_migrate = True
		try:
			self.assertFalse(is_field_hidden_by_app(frappe._dict(is_app_disabled=1)))
		finally:
			frappe.flags.in_migrate = False
