# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.patches.v17_0.move_list_view_widths_to_fields import execute as move_list_view_widths
from frappe.tests import IntegrationTestCase


class TestListViewSettings(IntegrationTestCase):
	def test_patch_moves_widths_to_the_fields(self):
		make_property_setter("ToDo", "priority", "width", "120", "Data", is_system_generated=False)
		self.addCleanup(frappe.delete_doc, "Property Setter", "ToDo-priority-width")
		self.addCleanup(frappe.delete_doc_if_exists, "Property Setter", "ToDo-status-width")
		self.save_list_view_settings(
			"ToDo",
			[
				{"fieldname": "status", "label": "Status", "width": 236.487},
				{"fieldname": "priority", "label": "Priority", "width": 180},
				{"fieldname": "status_field", "label": "Status", "width": 90},
				{"fieldname": "name", "label": "ID", "width": 120},
			],
		)

		move_list_view_widths()

		meta = frappe.get_meta("ToDo")
		self.assertEqual(meta.get_field("status").width, "236")
		self.assertEqual(meta.get_field("priority").width, "120")
		self.assertFalse(frappe.db.exists("Property Setter", {"doc_type": "ToDo", "field_name": "name"}))
		fields = json.loads(frappe.db.get_value("List View Settings", "ToDo", "fields"))
		self.assertEqual([field.get("width") for field in fields], [None, None, None, None])

	def test_patch_sets_the_width_on_a_custom_doctype(self):
		doctype = new_doctype(
			fields=[
				{"label": "Title", "fieldname": "title", "fieldtype": "Data"},
				{"label": "Code", "fieldname": "code", "fieldtype": "Data", "width": "90"},
			]
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "DocType", doctype.name, force=1)
		self.save_list_view_settings(
			doctype.name, [{"fieldname": "title", "width": 200}, {"fieldname": "code", "width": 150}]
		)

		move_list_view_widths()

		meta = frappe.get_meta(doctype.name)
		self.assertEqual(meta.get_field("title").width, "200")
		self.assertEqual(meta.get_field("code").width, "90")
		self.assertFalse(frappe.db.exists("Property Setter", {"doc_type": doctype.name}))

	def test_patch_sets_the_width_on_a_custom_field(self):
		field = create_custom_field(
			"Note", {"fieldname": "list_width_test", "label": "List Width Test", "fieldtype": "Data"}
		)
		self.addCleanup(frappe.db.drop_columns, "Note", ["list_width_test"])
		self.addCleanup(field.delete)
		self.save_list_view_settings("Note", [{"fieldname": "list_width_test", "width": 210}])

		move_list_view_widths()

		self.assertEqual(frappe.get_meta("Note").get_field("list_width_test").width, "210")
		self.assertFalse(
			frappe.db.exists("Property Setter", {"doc_type": "Note", "field_name": "list_width_test"})
		)

	def test_patch_drops_widths_of_a_core_doctype(self):
		self.save_list_view_settings("Role", [{"fieldname": "desk_access", "width": 150}])

		move_list_view_widths()

		self.assertFalse(frappe.db.exists("Property Setter", {"doc_type": "Role", "property": "width"}))
		fields = json.loads(frappe.db.get_value("List View Settings", "Role", "fields"))
		self.assertEqual(fields, [{"fieldname": "desk_access"}])

	def test_patch_skips_settings_of_a_deleted_doctype(self):
		self.save_list_view_settings("_Deleted DocType", [{"fieldname": "title", "width": 200}])

		move_list_view_widths()

		fields = json.loads(frappe.db.get_value("List View Settings", "_Deleted DocType", "fields"))
		self.assertEqual(fields, [{"fieldname": "title"}])

	def save_list_view_settings(self, doctype, fields):
		if frappe.db.exists("List View Settings", doctype):
			original = frappe.db.get_value("List View Settings", doctype, "fields")
			self.addCleanup(frappe.db.set_value, "List View Settings", doctype, "fields", original)
			frappe.db.set_value("List View Settings", doctype, "fields", json.dumps(fields))
		else:
			frappe.get_doc(doctype="List View Settings", name=doctype, fields=json.dumps(fields)).insert()
			self.addCleanup(frappe.delete_doc_if_exists, "List View Settings", doctype)
