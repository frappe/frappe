import os

import frappe
from frappe.studio.sync_json import get_component_path_from_script, get_doctype_from_path
from frappe.tests import IntegrationTestCase


class TestSyncJson(IntegrationTestCase):
	def test_an_app_file_is_found_under_a_hyphenated_folder(self):
		studio_folder = frappe.get_app_source_path("frappe", "studio")
		self.assertEqual(
			get_doctype_from_path(os.path.join(studio_folder, "my-app", "my_app.json")), "Studio App"
		)
		self.assertIsNone(get_doctype_from_path(os.path.join(studio_folder, "my-app", "my-app.json")))

	def test_a_component_is_found_in_an_app_and_in_the_frappe_app(self):
		studio_folder = frappe.get_app_source_path("frappe", "studio")
		for parts in (("my_app", "studio_components", "card.json"), ("studio_components", "card.json")):
			path = os.path.join(studio_folder, *parts)
			self.assertEqual(get_doctype_from_path(path), "Studio Component")
			self.assertEqual(get_component_path_from_script(path.replace(".json", ".js")), path)
