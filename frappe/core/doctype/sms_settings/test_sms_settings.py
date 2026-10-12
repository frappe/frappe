# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.sms_settings.sms_settings import check_sms_permission
from frappe.tests import IntegrationTestCase


class TestSMSSettings(IntegrationTestCase):
	def setUp(self):
		self.sms_settings = frappe.get_single("SMS Settings")
		self._allowed_roles = self.sms_settings.get("allowed_roles")
		self.sms_settings.set("allowed_roles", [])
		self.sms_settings.flags.ignore_mandatory = True
		self.sms_settings.save()

	def tearDown(self):
		frappe.set_user("Administrator")
		self.sms_settings.set("allowed_roles", self._allowed_roles)
		self.sms_settings.flags.ignore_mandatory = True
		self.sms_settings.save()

	def test_user_without_allowed_role_is_blocked(self):
		frappe.set_user("test@example.com")
		self.assertRaises(frappe.PermissionError, check_sms_permission)

	def test_system_manager_is_always_allowed(self):
		frappe.set_user("Administrator")
		check_sms_permission()

	def test_user_with_configured_role_is_allowed(self):
		self.sms_settings.append("allowed_roles", {"role": "System Manager"})
		self.sms_settings.flags.ignore_mandatory = True
		self.sms_settings.save()

		frappe.set_user("test@example.com")
		frappe.get_doc(
			{
				"doctype": "Has Role",
				"parent": "test@example.com",
				"parenttype": "User",
				"parentfield": "roles",
				"role": "System Manager",
			}
		).db_insert()
		frappe.clear_cache(user="test@example.com")

		check_sms_permission()

		frappe.db.delete("Has Role", {"parent": "test@example.com", "role": "System Manager"})
		frappe.clear_cache(user="test@example.com")
