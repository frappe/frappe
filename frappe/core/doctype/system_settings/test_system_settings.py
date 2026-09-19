# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.system_settings.system_settings import load
from frappe.tests import IntegrationTestCase


class TestSystemSettings(IntegrationTestCase):
	def test_load_returns_saved_value_over_stale_default(self):
		self.addCleanup(
			frappe.db.set_single_value,
			"System Settings",
			"time_zone",
			frappe.db.get_single_value("System Settings", "time_zone"),
		)
		self.addCleanup(frappe.db.set_default, "time_zone", frappe.db.get_default("time_zone"))

		frappe.db.set_single_value("System Settings", "time_zone", "Australia/Brisbane")
		frappe.db.set_default("time_zone", "Australia/Adelaide")

		with self.set_user("test@example.com"):
			self.assertEqual(load()["defaults"]["time_zone"], "Australia/Brisbane")
