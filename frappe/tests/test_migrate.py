# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.migrate import SiteMigration
from frappe.tests import IntegrationTestCase


class TestSiteMigration(IntegrationTestCase):
	def test_setup_rebuilds_module_map_from_modules_txt(self):
		frappe.local.app_modules = {
			app: [module for module in modules if module != "core"]
			for app, modules in frappe.local.app_modules.items()
		}
		self.addCleanup(setattr, frappe.flags, "in_migrate", False)

		with (
			patch.object(SiteMigration, "lower_lock_timeout"),
			patch.object(SiteMigration, "kill_idle_connections"),
		):
			SiteMigration().setUp()

		self.assertIn("core", frappe.local.app_modules["frappe"])
