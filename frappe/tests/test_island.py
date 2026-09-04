# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.island import get_island_assets, get_ui_islands

# The handlers the cases below declare. A `doc_events` handler is a dotted path,
# so these reach `run_method` the way an app's own does.
HERE = "frappe.tests.test_island"


def draws_the_dashboard(doc, method=None):
	doc.set_onload("island", {"name": "someapp.dashboard", "props": {"dashboard": doc.name}})


def draws_the_chart(doc, method=None):
	doc.set_onload("island", {"name": "someapp.chart", "props": {"chart": doc.name}})


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
		with patch.object(frappe.local, "request", None, create=True):
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


class TestIslandOnLoad(IntegrationTestCase):
	"""An app claims a desk document with a `doc_events` onload handler."""

	def patch_doc_events(self, doc_events):
		# `frappe.get_doc_hooks` caches its expansion on `frappe.local`, so the
		# patched hook only reaches `run_method` once the cache is gone.
		patched = self.patch_hooks({"doc_events": doc_events})
		frappe.local.doc_events_hooks = {}
		self.addCleanup(setattr, frappe.local, "doc_events_hooks", {})
		return patched

	def test_a_dashboard_an_app_draws_carries_the_island(self):
		dashboard = frappe.get_doc(doctype="Dashboard", dashboard_name=frappe.generate_hash()).insert()

		with self.patch_doc_events({"Dashboard": {"onload": f"{HERE}.draws_the_dashboard"}}):
			doc = frappe.get_doc("Dashboard", dashboard.name)
			doc.run_method("onload")

		self.assertEqual(
			doc.get_onload("island"),
			{"name": "someapp.dashboard", "props": {"dashboard": dashboard.name}},
		)

	def test_a_dashboard_no_app_draws_carries_no_island(self):
		dashboard = frappe.get_doc(doctype="Dashboard", dashboard_name=frappe.generate_hash()).insert()

		with self.patch_doc_events({}):
			doc = frappe.get_doc("Dashboard", dashboard.name)
			doc.run_method("onload")

		self.assertNotIn("island", doc.get_onload())

	def test_a_chart_an_app_draws_carries_the_island(self):
		chart = frappe.get_doc(
			doctype="Dashboard Chart",
			chart_name=frappe.generate_hash(),
			chart_type="Count",
			document_type="ToDo",
			based_on="creation",
			filters_json="[]",
		).insert()

		with self.patch_doc_events({"Dashboard Chart": {"onload": f"{HERE}.draws_the_chart"}}):
			doc = frappe.get_doc("Dashboard Chart", chart.name)
			doc.run_method("onload")

		self.assertEqual(
			doc.get_onload("island"),
			{"name": "someapp.chart", "props": {"chart": chart.name}},
		)
