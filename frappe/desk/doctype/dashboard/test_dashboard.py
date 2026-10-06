# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.core.doctype.user.test_user import test_user
from frappe.patches.v16_0.set_classic_dashboards import execute
from frappe.tests import IntegrationTestCase
from frappe.utils.modules import get_modules_from_all_apps_for_user


class TestDashboard(IntegrationTestCase):
	def test_permission_query(self):
		for user in ["Administrator", "test@example.com"]:
			with self.set_user(user):
				frappe.get_list("Dashboard")

		with test_user(roles=["_Test Role"]) as user:
			with self.set_user(user.name):
				frappe.get_list("Dashboard")
				with self.set_user("Administrator"):
					all_modules = get_modules_from_all_apps_for_user("Administrator")
					for module in all_modules:
						user.append("block_modules", {"module": module.get("module_name")})
					user.save()
				frappe.get_list("Dashboard")


class TestDashboardsOnUpgrade(IntegrationTestCase):
	"""Which dashboards an upgrading site lands on."""

	def setUp(self):
		self.original = frappe.db.get_single_value("System Settings", "dashboards")

	def tearDown(self):
		frappe.db.set_single_value("System Settings", "dashboards", self.original)

	def test_an_upgraded_site_opens_classic(self):
		frappe.db.set_single_value("System Settings", "dashboards", None)
		execute()
		self.assertEqual(frappe.db.get_single_value("System Settings", "dashboards"), "Classic")

	def test_a_site_before_the_setup_wizard_opens_insights(self):
		frappe.db.set_single_value("System Settings", "dashboards", None)
		with patch("frappe.is_setup_complete", return_value=False):
			execute()
		self.assertEqual(frappe.db.get_single_value("System Settings", "dashboards"), "Insights")
