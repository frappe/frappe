# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.patches.v17_0.move_list_view_widths_to_property_setters import (
	execute as move_list_view_widths,
)
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
			],
		)

		move_list_view_widths()

		meta = frappe.get_meta("ToDo")
		self.assertEqual(meta.get_field("status").width, "236")
		self.assertEqual(meta.get_field("priority").width, "120")
		fields = json.loads(frappe.db.get_value("List View Settings", "ToDo", "fields"))
		self.assertEqual([field.get("width") for field in fields], [None, None, None])

	def test_patch_skips_settings_of_a_deleted_doctype(self):
		self.save_list_view_settings("_Deleted DocType", [{"fieldname": "title", "width": 200}])

		move_list_view_widths()

		fields = json.loads(frappe.db.get_value("List View Settings", "_Deleted DocType", "fields"))
		self.assertEqual(fields, [{"fieldname": "title"}])

	def save_list_view_settings(self, doctype, fields):
		frappe.delete_doc_if_exists("List View Settings", doctype)
		frappe.get_doc(doctype="List View Settings", name=doctype, fields=json.dumps(fields)).insert()
		self.addCleanup(frappe.delete_doc_if_exists, "List View Settings", doctype)
