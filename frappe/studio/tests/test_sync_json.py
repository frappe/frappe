import os

import frappe
from frappe.studio.sync_json import get_doctype_from_path
from frappe.tests import IntegrationTestCase


class TestSyncJson(IntegrationTestCase):
	def test_an_app_file_is_found_under_a_hyphenated_folder(self):
		studio_folder = frappe.get_app_source_path("frappe", "studio")
		self.assertEqual(
			get_doctype_from_path(os.path.join(studio_folder, "my-app", "my_app.json")), "Studio App"
		)
		self.assertIsNone(get_doctype_from_path(os.path.join(studio_folder, "my-app", "my-app.json")))
