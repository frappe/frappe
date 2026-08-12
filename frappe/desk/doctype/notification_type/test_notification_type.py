# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.notification_type.notification_type import (
	BUILTIN_NOTIFICATION_TYPES,
	install_notification_types,
)
from frappe.tests import IntegrationTestCase


class TestNotificationType(IntegrationTestCase):
	def test_builtin_types_seeded(self):
		install_notification_types()
		for definition in BUILTIN_NOTIFICATION_TYPES:
			self.assertTrue(
				frappe.db.exists("Notification Type", definition["type_name"]),
				msg=f"Built-in Notification Type {definition['type_name']} not seeded",
			)

	def test_seeder_is_idempotent(self):
		install_notification_types()
		before = frappe.db.count("Notification Type", {"name": "Mention"})
		install_notification_types()
		after = frappe.db.count("Notification Type", {"name": "Mention"})
		self.assertEqual(before, after, 1)

	def test_builtin_type_cannot_be_deleted(self):
		install_notification_types()
		self.assertRaises(frappe.ValidationError, frappe.delete_doc, "Notification Type", "Alert")

	def test_custom_type_can_be_deleted(self):
		frappe.get_doc({"doctype": "Notification Type", "type_name": "Temp Custom Type"}).insert(
			ignore_permissions=True
		)
		# should not raise
		frappe.delete_doc("Notification Type", "Temp Custom Type")
		self.assertFalse(frappe.db.exists("Notification Type", "Temp Custom Type"))

	def test_get_notification_types_returns_enabled_types(self):
		install_notification_types()
		types = {
			t["name"]: t
			for t in frappe.call(
				"frappe.desk.doctype.notification_type.notification_type.get_notification_types"
			)
		}
		self.assertIn("Mention", types)
		self.assertEqual(types["Mention"]["type_name"], "Mention")
		self.assertTrue(types["Mention"]["enabled"])
