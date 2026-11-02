import os
from unittest.mock import patch

import frappe
from frappe.studio.api import (
	create_studio_file,
	get_custom_vue_components,
	get_studio_page_scripts,
	read_studio_file,
	write_studio_file,
)
from frappe.studio.doctype.studio_app.test_studio_app import make_studio_app
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

	def test_discovery_endpoints_accept_only_installed_apps(self):
		self.assertRaises(frappe.ValidationError, get_custom_vue_components, "os")
		self.assertRaises(frappe.ValidationError, get_studio_page_scripts, "os")

	def test_file_requests_stay_inside_an_exported_app(self):
		with exports_in_tempdir(), patch.dict(frappe.conf, {"developer_mode": 1}):
			self.assertRaises(
				frappe.PermissionError,
				read_studio_file,
				"frappe",
				"../../..",
				"sites/common_site_config.json",
			)

	def test_the_build_config_cannot_be_written_from_the_editor(self):
		with exports_in_tempdir(), patch.dict(frappe.conf, {"developer_mode": 1}):
			app = make_studio_app(
				app_name="cfg-" + frappe.generate_hash(length=8), is_standard=1, frappe_app="frappe"
			)
			for file_path in ("tailwind.config.js", "Tailwind.Config.js"):
				for call in (
					lambda: write_studio_file("frappe", app.name, file_path, "module.exports = {}"),
					lambda: create_studio_file("frappe", app.name, file_path),
				):
					self.assertRaises(frappe.ValidationError, call)
