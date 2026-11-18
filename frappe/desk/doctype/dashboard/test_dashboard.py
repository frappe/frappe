# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json
import os
import shutil
import tempfile
from unittest.mock import patch

import frappe
from frappe.core.doctype.user.test_user import test_user
from frappe.desk.doctype.dashboard.dashboard import (
	SKIP_INSIGHTS_DASHBOARDS_PROMPT,
	get_insights_dashboards_prompt,
	should_show_insights_dashboards_prompt,
	submit_insights_dashboards_prompt,
)
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
			lambda module, *joins: os.path.join(self.module_path, *(frappe.scrub(j) for j in joins)),
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


class TestInsightsDashboardsPrompt(IntegrationTestCase):
	"""A site that draws classic dashboards tells its System Managers once about the Insights ones."""

	def setUp(self):
		self.original = frappe.db.get_single_value("System Settings", "dashboards")
		frappe.db.set_single_value("System Settings", "dashboards", "Classic")
		frappe.defaults.clear_default(SKIP_INSIGHTS_DASHBOARDS_PROMPT)

	def tearDown(self):
		frappe.db.set_single_value("System Settings", "dashboards", self.original)
		frappe.defaults.clear_default(SKIP_INSIGHTS_DASHBOARDS_PROMPT)

	def test_it_asks_a_system_manager(self):
		self.assertTrue(should_show_insights_dashboards_prompt())

	def test_it_asks_nobody_else(self):
		with test_user(roles=["_Test Role"]) as user, self.set_user(user.name):
			self.assertFalse(should_show_insights_dashboards_prompt())

	def test_the_choice_does_not_decide_the_prompt(self):
		frappe.db.set_single_value("System Settings", "dashboards", "Insights")
		self.assertTrue(should_show_insights_dashboards_prompt())

	def site_calls_for(self, prompt: str):
		return patch(
			"frappe.desk.doctype.dashboard.dashboard.get_insights_dashboards_prompt", return_value=prompt
		)

	def test_the_prompt_follows_the_site_insights(self):
		for field, apps, prompt in (
			(None, ["frappe"], "install"),
			(None, ["frappe", "insights"], "update"),
			(frappe._dict(fieldname="insights_dashboard"), ["frappe", "insights"], "switch"),
		):
			with (
				patch.object(frappe.get_meta("Dashboard"), "get_field", return_value=field),
				patch("frappe.get_installed_apps", return_value=apps),
			):
				self.assertEqual(get_insights_dashboards_prompt(), prompt)

	def test_dismissing_one_prompt_leaves_the_later_ones(self):
		for dismissed, later in (("install", ("update", "switch")), ("update", ("switch",))):
			frappe.defaults.clear_default(SKIP_INSIGHTS_DASHBOARDS_PROMPT)
			with self.site_calls_for(dismissed):
				submit_insights_dashboards_prompt("keep_classic_dashboards")
				self.assertFalse(should_show_insights_dashboards_prompt())
			for prompt in later:
				with self.site_calls_for(prompt):
					self.assertTrue(should_show_insights_dashboards_prompt())

	def test_dismissing_the_switch_leaves_no_prompt(self):
		with self.site_calls_for("switch"):
			submit_insights_dashboards_prompt("keep_classic_dashboards")
		for prompt in ("install", "update", "switch"):
			with self.site_calls_for(prompt):
				self.assertFalse(should_show_insights_dashboards_prompt())

	def test_a_dismissal_from_before_the_variants_still_asks_to_switch(self):
		frappe.defaults.set_global_default(SKIP_INSIGHTS_DASHBOARDS_PROMPT, 1)
		with self.site_calls_for("install"):
			self.assertFalse(should_show_insights_dashboards_prompt())
		with self.site_calls_for("switch"):
			self.assertTrue(should_show_insights_dashboards_prompt())

	def test_dismissing_a_prompt_left_open_answers_only_that_prompt(self):
		# The page showed Update, and Insights was updated before the click.
		with self.site_calls_for("switch"):
			submit_insights_dashboards_prompt("keep_classic_dashboards", "update")
			self.assertTrue(should_show_insights_dashboards_prompt())

			submit_insights_dashboards_prompt("keep_classic_dashboards", "install")
			self.assertTrue(should_show_insights_dashboards_prompt())
			self.assertRaises(
				frappe.ValidationError, submit_insights_dashboards_prompt, "keep_classic_dashboards", "other"
			)

	def test_keeping_classic_switches_nothing(self):
		submit_insights_dashboards_prompt("keep_classic_dashboards")
		self.assertFalse(should_show_insights_dashboards_prompt())
		self.assertEqual(frappe.db.get_single_value("System Settings", "dashboards"), "Classic")

	def test_opening_insights_switches_the_site_and_is_final(self):
		with self.site_calls_for("switch"):
			submit_insights_dashboards_prompt("open_insights_dashboards")
			self.assertEqual(frappe.db.get_single_value("System Settings", "dashboards"), "Insights")

			frappe.db.set_single_value("System Settings", "dashboards", "Classic")
			self.assertFalse(should_show_insights_dashboards_prompt())

	def test_someone_else_cannot_answer_for_the_site(self):
		with test_user(roles=["_Test Role"]) as user, self.set_user(user.name):
			self.assertRaises(
				frappe.PermissionError, submit_insights_dashboards_prompt, "keep_classic_dashboards"
			)

	def test_an_insights_version_carries_the_prompt_without_insights(self):
		doc = frappe.get_doc({"doctype": "Dashboard", "name": "Test Prompt"})
		with (
			patch.object(type(doc), "has_insights_version", return_value=True),
			patch.object(doc.meta, "get_field", return_value=None),
			patch("frappe.get_installed_apps", return_value=["frappe"]),
		):
			doc.run_method("onload")
			self.assertEqual(doc.get_onload().get("show_insights_dashboards_prompt"), "install")

			submit_insights_dashboards_prompt("keep_classic_dashboards")
			doc = frappe.get_doc({"doctype": "Dashboard", "name": "Test Prompt"})
			doc.run_method("onload")
			self.assertNotIn("show_insights_dashboards_prompt", doc.get_onload())

	def test_a_dashboard_insights_installs_no_board_for_carries_no_prompt(self):
		doc = frappe.get_doc({"doctype": "Dashboard", "name": "Test Prompt"})
		with (
			patch.object(type(doc), "has_insights_version", return_value=True),
			patch.object(doc.meta, "get_field", return_value=frappe._dict(options="User")),
		):
			doc.run_method("onload")
		self.assertEqual(doc.get_onload().get("dashboards"), "Classic")
		self.assertNotIn("show_insights_dashboards_prompt", doc.get_onload())
