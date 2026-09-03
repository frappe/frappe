# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
import frappe.defaults
from frappe.tests import IntegrationTestCase

from .setup_wizard import set_timezone


class TestSetupWizard(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.original_user_timezones = {
			user: frappe.db.get_value("User", user, "time_zone") for user in frappe.STANDARD_USERS
		}
		self.original_defaults = {
			user: frappe.db.get_value(
				"DefaultValue", {"parent": user, "defkey": "time_zone"}, "defvalue"
			)
			for user in frappe.STANDARD_USERS
		}
		self.addCleanup(self.restore_standard_user_timezones)

	def restore_standard_user_timezones(self):
		for user in frappe.STANDARD_USERS:
			frappe.db.set_value(
				"User", user, "time_zone", self.original_user_timezones[user], update_modified=False
			)
			if self.original_defaults[user] is None:
				frappe.defaults.clear_default("time_zone", parent=user)
			else:
				frappe.defaults.set_default("time_zone", self.original_defaults[user], user)

	def test_set_timezone_updates_standard_user_defaults(self):
		old_timezone = "Asia/Kolkata"
		new_timezone = "Africa/Nairobi"

		for user in frappe.STANDARD_USERS:
			frappe.db.set_value("User", user, "time_zone", old_timezone, update_modified=False)
			frappe.defaults.set_default("time_zone", old_timezone, user)

		set_timezone(new_timezone)

		for user in frappe.STANDARD_USERS:
			self.assertEqual(frappe.db.get_value("User", user, "time_zone"), new_timezone)
			self.assertEqual(frappe.defaults.get_user_default("time_zone", user), new_timezone)
