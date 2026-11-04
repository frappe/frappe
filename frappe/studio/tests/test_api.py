import os
from unittest.mock import patch

import frappe
from frappe.studio.api import (
	create_studio_file,
	get_app_files,
	get_custom_vue_components,
	get_studio_page_scripts,
	list_studio_files,
	read_studio_file,
	write_studio_file,
)
from frappe.studio.doctype.studio_app.test_studio_app import make_studio_app, make_studio_page
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

	def test_the_file_explorer_reaches_a_database_app_without_developer_mode(self):
		app = make_studio_app(app_name="store-" + frappe.generate_hash(length=8))
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			create_studio_file("", app.name, "utils/format.ts")
			write_studio_file("", app.name, "utils/format.ts", "export const one = 1\n")
			self.assertEqual(
				read_studio_file("", app.name, "utils/format.ts")["content"], "export const one = 1\n"
			)
			self.assertEqual(list_studio_files("", app.name)[0]["path"], "utils")

		# The same request requires developer mode when the source is in a repository.
		with exports_in_tempdir():
			repo_app = make_studio_app(
				app_name="repo-" + frappe.generate_hash(length=8), is_standard=1, frappe_app="frappe"
			)
			with patch.dict(frappe.conf, {"developer_mode": 0}):
				self.assertRaises(frappe.ValidationError, list_studio_files, "frappe", repo_app.name)

	def test_app_files_are_served_only_to_someone_who_may_see_the_app(self):
		app = make_studio_app(app_name="served-" + frappe.generate_hash(length=8))
		write_studio_file("", app.name, "components/Card.vue", "<template><b>hi</b></template>\n")

		served = get_app_files(app.name)
		self.assertEqual([file["path"] for file in served], ["components/Card.vue"])
		self.assertEqual(served[0]["content"], "<template><b>hi</b></template>\n")

		# Guests need a published page that allows guest access.
		with self.set_user("Guest"):
			self.assertRaises(frappe.PermissionError, get_app_files, app.name)
		make_studio_page(app.name, published=1, allow_guest=1)
		with self.set_user("Guest"):
			self.assertEqual(len(get_app_files(app.name)), 1)

	def test_a_database_app_lists_its_components_to_everyone_it_serves_files_to(self):
		# Viewers who can load Vue source also need component names to render the app.
		app = make_studio_app(app_name="vue-" + frappe.generate_hash(length=8))
		write_studio_file("", app.name, "components/Card.vue", "<template><b>hi</b></template>\n")
		make_studio_page(app.name, published=1, allow_guest=1)

		for user in ("test@example.com", "Guest"):
			with self.set_user(user):
				self.assertEqual(
					[c["component_name"] for c in get_custom_vue_components(studio_app=app.name)],
					["Card"],
					msg=user,
				)

	def test_only_an_editor_can_enumerate_components_on_disk(self):
		# Disk component metadata includes server paths and requires editor permissions.
		with self.set_user("Guest"):
			self.assertRaises(frappe.PermissionError, get_custom_vue_components, "frappe")

	def test_a_repository_app_serves_no_files_to_the_browser(self):
		with exports_in_tempdir():
			app = make_studio_app(
				app_name="built-" + frappe.generate_hash(length=8), is_standard=1, frappe_app="frappe"
			)
			self.assertEqual(get_app_files(app.name), [])
