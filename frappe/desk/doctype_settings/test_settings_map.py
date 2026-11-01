# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE

import frappe
from frappe.desk.doctype_settings.settings_map import get_settings_map
from frappe.tests import IntegrationTestCase


class TestSettingsMap(IntegrationTestCase):
	def test_table_field_is_skipped(self):
		frappe.get_doc(
			{
				"doctype": "DocType Settings Map",
				"applies_to_doctype": "ToDo",
				"is_active": 1,
				"mappings": [
					{"settings_doctype": "Navbar Settings", "setting_field": "app_logo"},
					{"settings_doctype": "Navbar Settings", "setting_field": "settings_dropdown"},
				],
			}
		).insert()
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")

		fields = get_settings_map("ToDo")[0]["fields"]

		self.assertEqual([field["fieldname"] for field in fields], ["app_logo"])
