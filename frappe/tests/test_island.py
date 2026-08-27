# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.island import get_ui_islands


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
