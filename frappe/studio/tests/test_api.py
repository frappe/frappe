import os
from unittest.mock import patch

import frappe
from frappe.studio.api import get_custom_vue_components, read_studio_file
from frappe.studio.doctype.studio_page.test_studio_page import exports_in_tempdir
from frappe.tests import IntegrationTestCase


class TestApi(IntegrationTestCase):
	def test_custom_components_come_only_from_studio_apps(self):
		with exports_in_tempdir():
			editor_src = frappe.get_app_source_path("frappe", "studio", "frontend", "src")
			os.makedirs(editor_src)
			with open(os.path.join(editor_src, "Toolbar.vue"), "w") as f:
				f.write("<template><div /></template>")

			self.assertEqual(get_custom_vue_components("frappe"), [])

	def test_file_requests_stay_inside_an_exported_app(self):
		with exports_in_tempdir(), patch.dict(frappe.conf, {"developer_mode": 1}):
			self.assertRaises(
				frappe.PermissionError,
				read_studio_file,
				"frappe",
				"../../..",
				"sites/common_site_config.json",
			)
