import json
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

APP_ROOT = Path(frappe.get_app_path("frappe"))


def shipped(folder: str) -> list[dict]:
	return [json.loads(path.read_text()) for path in sorted((APP_ROOT / folder).glob("*/*.json"))]


class TestFrappeNavigation(IntegrationTestCase):
	"""The rail and sidebars the framework ships open real sidebars and real doctypes."""

	def test_every_rail_row_opens_a_shipped_sidebar(self):
		names = {sidebar["name"] for sidebar in shipped("sidebar")}
		rail = shipped("rail")[0]["items"]

		self.assertTrue(rail)
		self.assertEqual({row["link_to"] for row in rail} - names, set())

	def test_every_sidebar_row_names_a_doctype_that_exists(self):
		for sidebar in shipped("sidebar"):
			for row in sidebar["navigation_items"]:
				if row["item_type"] == "DocType":
					self.assertTrue(frappe.db.exists("DocType", row["link_to"]), (sidebar["name"], row["key"]))

	def test_keys_are_unique_within_a_sidebar_and_parents_exist(self):
		for sidebar in shipped("sidebar"):
			keys = [row["key"] for row in sidebar["navigation_items"]]
			self.assertEqual(len(keys), len(set(keys)), sidebar["name"])
			parents = {row["parent_key"] for row in sidebar["navigation_items"] if row.get("parent_key")}
			self.assertEqual(parents - set(keys), set(), sidebar["name"])
