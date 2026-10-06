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


class TestUiIslandsRegistry(IntegrationTestCase):
	"""A build registers an island by writing its asset key."""

	def patch_assets_json(self, assets):
		return patch("frappe.utils.island.get_assets_json", return_value=assets)

	def test_the_name_is_the_key_without_the_suffix(self):
		with self.patch_assets_json(
			{"frappe.dashboard.island.js": "/assets/frappe/dist/island/dashboard.js"}
		):
			self.assertEqual(get_ui_islands(), ["frappe.dashboard"])

	def test_a_key_of_any_other_form_is_not_an_island(self):
		with self.patch_assets_json(
			{
				"insights.dashboard.island.css": "/assets/insights/dist/island/dashboard.css",
				"desk.bundle.js": "/assets/frappe/dist/js/desk.bundle.js",
				"frappe/images/logo.svg": "/assets/frappe/images/logo.svg",
			}
		):
			self.assertEqual(get_ui_islands(), [])

	def test_an_island_of_an_app_this_site_lacks_is_left_out(self):
		# assets.json is bench-wide, and a site holds a subset of the bench's apps.
		with self.patch_assets_json(
			{
				"frappe.example.island.js": "/assets/frappe/dist/island/example.js",
				"nosuchapp.example.island.js": "/assets/nosuchapp/dist/island/example.js",
			}
		):
			self.assertEqual(get_ui_islands(), ["frappe.example"])

	def test_the_registry_reaches_the_browser_through_boot(self):
		# The desk loader resolves island names on the client, so boot must carry them.
		with patch.object(frappe.local, "request", None, create=True):
			self.assertIn("ui_islands", frappe.sessions.get())


class TestIslandAssets(IntegrationTestCase):
	def patch_assets_json(self, assets):
		return patch("frappe.utils.island.get_assets_json", return_value=assets)

	def test_an_island_resolves_to_its_js_and_css(self):
		with self.patch_assets_json(
			{
				"frappe.example.island.js": "/assets/frappe/dist/island/example.js",
				"frappe.example.island.css": "/assets/frappe/dist/island/example.css",
			}
		):
			self.assertEqual(
				get_island_assets("frappe.example"),
				{
					"js": "/assets/frappe/dist/island/example.js",
					"css": "/assets/frappe/dist/island/example.css",
				},
			)

	def test_an_island_without_css_resolves_to_none(self):
		with self.patch_assets_json({"frappe.example.island.js": "/assets/frappe/dist/island/example.js"}):
			self.assertIsNone(get_island_assets("frappe.example")["css"])

	def test_an_unbuilt_island_throws(self):
		with self.patch_assets_json({}):
			with self.assertRaises(frappe.ValidationError):
				get_island_assets("frappe.example")

	def test_an_island_of_an_app_this_site_lacks_throws(self):
		with self.patch_assets_json(
			{"nosuchapp.example.island.js": "/assets/nosuchapp/dist/island/example.js"}
		):
			with self.assertRaises(frappe.ValidationError):
				get_island_assets("nosuchapp.example")


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
