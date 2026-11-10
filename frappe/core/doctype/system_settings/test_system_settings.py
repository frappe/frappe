# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.cache_manager import clear_defaults_cache
from frappe.core.doctype.system_settings.system_settings import load
from frappe.core.doctype.user_permission.test_user_permission import create_user
from frappe.tests import IntegrationTestCase


class TestSystemSettings(IntegrationTestCase):
	def test_load_returns_saved_value_over_stale_default(self):
		user = create_user("system-settings-reader@example.com", "System Manager")
		self.addCleanup(frappe.clear_cache, user=user.name)
		self.addCleanup(frappe.clear_document_cache, "System Settings", "System Settings")
		self.addCleanup(clear_defaults_cache, "__default")

		frappe.db.set_single_value("System Settings", "time_zone", "Australia/Brisbane")
		frappe.db.set_default("time_zone", "Australia/Adelaide")

		with self.set_user(user.name):
			self.assertEqual(load()["defaults"]["time_zone"], "Australia/Brisbane")


class TestClassicChartsOnUpgrade(IntegrationTestCase):
	PATCH = "frappe.patches.v17_0.keep_existing_sites_on_classic_charts"

	def setUp(self):
		self.addCleanup(
			frappe.db.set_single_value,
			"System Settings",
			"use_classic_charts",
			frappe.db.get_single_value("System Settings", "use_classic_charts"),
		)
		self.addCleanup(
			frappe.db.set_default, "use_classic_charts", frappe.db.get_default("use_classic_charts")
		)
		frappe.db.set_single_value("System Settings", "use_classic_charts", 0)
		frappe.db.set_default("use_classic_charts", 0)

	def test_an_upgrading_site_keeps_classic_charts(self):
		with patch("frappe.is_setup_complete", return_value=True):
			frappe.get_attr(self.PATCH + ".execute")()

		self.assertEqual(frappe.db.get_single_value("System Settings", "use_classic_charts"), 1)
		self.assertEqual(frappe.defaults.get_defaults()["use_classic_charts"], "1")

	def test_a_site_before_the_setup_wizard_gets_the_new_charts(self):
		with patch("frappe.is_setup_complete", return_value=False):
			frappe.get_attr(self.PATCH + ".execute")()

		self.assertEqual(frappe.db.get_single_value("System Settings", "use_classic_charts"), 0)
		self.assertEqual(frappe.defaults.get_defaults()["use_classic_charts"], "0")
