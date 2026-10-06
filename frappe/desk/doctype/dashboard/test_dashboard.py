# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json
import os
import shutil
import tempfile
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


class TestDashboardView(IntegrationTestCase):
	"""What a standard dashboard with an Insights version tells the page about the site's choice."""

	def setUp(self):
		self.original = frappe.db.get_single_value("System Settings", "dashboards")
		self.module_path = tempfile.mkdtemp()

	def tearDown(self):
		frappe.db.set_single_value("System Settings", "dashboards", self.original)
		shutil.rmtree(self.module_path)

	def dashboard(self, shipped: dict | None, is_standard=1):
		"""An unsaved Dashboard, and the file its app ships for it."""
		doc = frappe.get_doc(
			{"doctype": "Dashboard", "name": "Test View Rule", "is_standard": is_standard, "module": "Desk"}
		)
		if shipped is not None:
			folder = os.path.join(self.module_path, "desk_dashboard", "test_view_rule")
			os.makedirs(folder)
			with open(os.path.join(folder, "test_view_rule.json"), "w") as f:
				json.dump(shipped, f)
		return doc

	def onload(self, doc) -> dict:
		with patch(
			"frappe.get_module_path",
			lambda module, *joins: os.path.join(self.module_path, *map(frappe.scrub, joins)),
		):
			doc.run_method("onload")
		return doc.get_onload()

	def test_an_insights_version_carries_the_site_choice(self):
		doc = self.dashboard({"insights_dashboard": "test_view_rule"})
		for choice in ("Insights", "Classic"):
			frappe.db.set_single_value("System Settings", "dashboards", choice)
			self.assertEqual(self.onload(doc).get("dashboards"), choice)

	def test_a_dashboard_without_an_insights_version_carries_nothing(self):
		self.assertNotIn("dashboards", self.onload(self.dashboard({"name": "Test View Rule"})))

	def test_a_custom_dashboard_carries_nothing(self):
		doc = self.dashboard({"insights_dashboard": "test_view_rule"}, is_standard=0)
		self.assertNotIn("dashboards", self.onload(doc))

	def test_a_dashboard_in_a_custom_module_carries_nothing(self):
		doc = frappe.get_doc(
			{
				"doctype": "Dashboard",
				"name": "Test View Rule",
				"is_standard": 1,
				"module": "Custom Test Module",
			}
		)
		doc.run_method("onload")
		self.assertNotIn("dashboards", doc.get_onload())
