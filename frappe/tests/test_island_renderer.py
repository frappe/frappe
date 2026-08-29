# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import MagicMock, patch

import frappe
from frappe.desk.island_renderer import ONLOAD_KEY, resolve_island_renderer, set_island_renderer
from frappe.tests import IntegrationTestCase

# The renderers the cases below declare. An app's hook is a dotted path, so these
# reach the resolver the way a real one does and nothing needs `frappe.get_attr`
# patched.
HERE = "frappe.tests.test_island_renderer"


def draws(doc):
	return {"island": "someapp.dashboard", "props": {"dashboard": doc.name}}


def draws_too(doc):
	return {"island": "otherapp.dashboard", "props": {}}


def draws_nothing(doc):
	return None


def draws_without_props(doc):
	return {"island": "someapp.dashboard"}


def returns_a_string(doc):
	return "someapp.dashboard"


def returns_no_island(doc):
	return {"props": {"dashboard": doc.name}}


def returns_bad_props(doc):
	return {"island": "someapp.dashboard", "props": "dashboard=sales"}


class TestIslandRenderer(IntegrationTestCase):
	def setUp(self):
		# A dashboard with no charts, which is what an island-drawn dashboard is.
		self.dashboard = frappe.get_doc(doctype="Dashboard", dashboard_name=frappe.generate_hash()).insert()

	def test_no_app_declares_the_hook(self):
		with self.patch_hooks({"dashboard_renderer": []}):
			self.assertIsNone(resolve_island_renderer(self.dashboard, "dashboard_renderer"))

	def test_a_renderer_that_draws_nothing(self):
		with self.patch_hooks({"dashboard_renderer": [f"{HERE}.draws_nothing"]}):
			self.assertIsNone(resolve_island_renderer(self.dashboard, "dashboard_renderer"))

	def test_a_renderer_that_draws_the_document(self):
		with self.patch_hooks({"dashboard_renderer": [f"{HERE}.draws"]}):
			self.assertEqual(
				resolve_island_renderer(self.dashboard, "dashboard_renderer"),
				{"island": "someapp.dashboard", "props": {"dashboard": self.dashboard.name}},
			)

	def test_props_are_optional(self):
		with self.patch_hooks({"dashboard_renderer": [f"{HERE}.draws_without_props"]}):
			self.assertEqual(
				resolve_island_renderer(self.dashboard, "dashboard_renderer"),
				{"island": "someapp.dashboard", "props": {}},
			)

	def test_the_first_of_two_competing_apps_draws_the_document(self):
		with self.patch_hooks({"dashboard_renderer": [f"{HERE}.draws", f"{HERE}.draws_too"]}):
			with patch.object(frappe, "logger", return_value=MagicMock()) as logger:
				renderer = resolve_island_renderer(self.dashboard, "dashboard_renderer")

		self.assertEqual(renderer["island"], "someapp.dashboard")

		# The collision is a bug on the app side, so the warning names both methods.
		warning = logger.return_value.warning.call_args[0][0]
		self.assertIn(f"{HERE}.draws", warning)
		self.assertIn(f"{HERE}.draws_too", warning)

	def test_an_app_that_draws_nothing_is_not_a_collision(self):
		with self.patch_hooks({"dashboard_renderer": [f"{HERE}.draws_nothing", f"{HERE}.draws_too"]}):
			with patch.object(frappe, "logger", return_value=MagicMock()) as logger:
				renderer = resolve_island_renderer(self.dashboard, "dashboard_renderer")

		self.assertEqual(renderer["island"], "otherapp.dashboard")
		logger.return_value.warning.assert_not_called()

	def test_a_malformed_return_raises(self):
		for method in ("returns_a_string", "returns_no_island", "returns_bad_props"):
			with self.subTest(method=method), self.patch_hooks({"dashboard_renderer": [f"{HERE}.{method}"]}):
				with self.assertRaises(frappe.ValidationError):
					resolve_island_renderer(self.dashboard, "dashboard_renderer")

	def test_onload_carries_the_renderer(self):
		with self.patch_hooks({"dashboard_renderer": [f"{HERE}.draws"]}):
			set_island_renderer(self.dashboard, "dashboard_renderer")

		self.assertEqual(
			self.dashboard.get_onload(ONLOAD_KEY),
			{"island": "someapp.dashboard", "props": {"dashboard": self.dashboard.name}},
		)

	def test_onload_carries_no_key_while_no_app_draws_the_document(self):
		with self.patch_hooks({"dashboard_renderer": []}):
			set_island_renderer(self.dashboard, "dashboard_renderer")

		self.assertNotIn(ONLOAD_KEY, self.dashboard.get_onload())

	def test_the_dashboard_doctype_resolves_on_load(self):
		with self.patch_hooks({"dashboard_renderer": [f"{HERE}.draws"]}):
			dashboard = frappe.get_doc("Dashboard", self.dashboard.name)
			dashboard.run_method("onload")

		self.assertEqual(dashboard.get_onload(ONLOAD_KEY)["island"], "someapp.dashboard")

	def test_the_dashboard_chart_doctype_resolves_on_load(self):
		chart = frappe.get_doc(
			doctype="Dashboard Chart",
			chart_name=frappe.generate_hash(),
			chart_type="Count",
			document_type="ToDo",
			based_on="creation",
			filters_json="[]",
		).insert()

		with self.patch_hooks({"dashboard_chart_renderer": [f"{HERE}.draws"]}):
			chart = frappe.get_doc("Dashboard Chart", chart.name)
			chart.run_method("onload")

		self.assertEqual(chart.get_onload(ONLOAD_KEY)["island"], "someapp.dashboard")
