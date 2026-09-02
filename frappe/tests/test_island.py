# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.island import get_island_assets, get_ui_islands


class TestUiIslandsRegistry(IntegrationTestCase):
	def test_registry_unwraps_the_hook_lists(self):
		with self.patch_hooks({"ui_islands": {"insights.dashboard": ["insights_dashboard"]}}):
			self.assertEqual(get_ui_islands(), {"insights.dashboard": "insights_dashboard"})

	def test_registry_merges_islands_of_several_apps(self):
		with self.patch_hooks(
			{
				"ui_islands": {
					"insights.dashboard": ["insights_dashboard"],
					"helpdesk.ticket": ["helpdesk_ticket"],
				}
			}
		):
			self.assertEqual(
				get_ui_islands(),
				{
					"insights.dashboard": "insights_dashboard",
					"helpdesk.ticket": "helpdesk_ticket",
				},
			)

	def test_last_app_to_declare_a_name_wins(self):
		with self.patch_hooks({"ui_islands": {"insights.dashboard": ["original", "override"]}}):
			self.assertEqual(get_ui_islands(), {"insights.dashboard": "override"})

	def test_registry_is_empty_without_the_hook(self):
		with self.patch_hooks({"ui_islands": {}}):
			self.assertEqual(get_ui_islands(), {})

	def test_registry_reaches_the_browser_through_boot(self):
		# The loader resolves island names on the client, so boot must carry them.
		frappe.local.request = None
		self.addCleanup(lambda: delattr(frappe.local, "request"))
		self.assertIn("ui_islands", frappe.sessions.get())


class TestIslandAssets(IntegrationTestCase):
	def patch_assets_json(self, assets):
		return patch("frappe.utils.island.get_assets_json", return_value=assets)

	def test_declared_island_resolves_to_its_js_and_css(self):
		with self.patch_hooks({"ui_islands": {"insights.dashboard": ["insights_dashboard"]}}):
			with self.patch_assets_json(
				{
					"insights_dashboard.island.js": "/assets/insights/dist/js/insights_dashboard.island.js",
					"insights_dashboard.island.css": "/assets/insights/dist/css/insights_dashboard.island.css",
				}
			):
				self.assertEqual(
					get_island_assets("insights.dashboard"),
					{
						"js": "/assets/insights/dist/js/insights_dashboard.island.js",
						"css": "/assets/insights/dist/css/insights_dashboard.island.css",
					},
				)

	def test_island_without_css_resolves_to_none(self):
		with self.patch_hooks({"ui_islands": {"insights.dashboard": ["insights_dashboard"]}}):
			with self.patch_assets_json({"insights_dashboard.island.js": "/assets/js.js"}):
				self.assertIsNone(get_island_assets("insights.dashboard")["css"])

	def test_undeclared_island_throws(self):
		with self.patch_hooks({"ui_islands": {}}), self.patch_assets_json({}):
			with self.assertRaises(frappe.ValidationError):
				get_island_assets("insights.dashboard")

	def test_unbuilt_bundle_throws(self):
		with self.patch_hooks({"ui_islands": {"insights.dashboard": ["insights_dashboard"]}}):
			with self.patch_assets_json({}):
				with self.assertRaises(frappe.ValidationError):
					get_island_assets("insights.dashboard")
