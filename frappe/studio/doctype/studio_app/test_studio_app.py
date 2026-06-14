# Copyright (c) 2024, Frappe Technologies Pvt Ltd and Contributors
# See license.txt

import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_files_path

from studio.build import StudioAppBuilder, get_published_custom_apps


class TestStudioApp(FrappeTestCase):
	def test_studio_app_creation(self):
		app = make_studio_app(app_title="My Build App", app_name="my-build-app")
		self.assertEqual(app.app_title, "My Build App")
		self.assertEqual(app.route, "my-build-app")


class TestStudioAppBuilder(FrappeTestCase):
	"""Tests build orchestration."""

	def test_extracts_nested_children_components(self):
		app = make_studio_app(app_title="Nested App", app_name="nested-app")
		blocks = json.dumps(
			[
				{
					"componentName": "Alert",
					"children": [
						{"componentName": "Badge", "children": []},
						{
							"componentName": "div",
							"children": [{"componentName": "Avatar", "children": []}],
						},
					],
				}
			]
		)
		make_studio_page(app.name, page_title="Nested Page", blocks=blocks, published=1)

		builder = StudioAppBuilder(app.name, is_standard=False)
		builder.get_app_components()
		self.assertIn("Alert", builder.components)
		self.assertIn("Badge", builder.components)
		self.assertIn("Avatar", builder.components)
		self.assertNotIn("div", builder.components)

	def test_extracts_components_from_slots(self):
		app = make_studio_app(app_title="Slot App", app_name="slot-app")
		blocks = json.dumps(
			[
				{
					"componentName": "Dialog",
					"children": [],
					"componentSlots": {
						"default": {
							"slotContent": [
								{"componentName": "TextInput", "children": []},
							]
						}
					},
				}
			]
		)
		make_studio_page(app.name, page_title="Slot Page", blocks=blocks, published=1)

		builder = StudioAppBuilder(app.name, is_standard=False)
		builder.get_app_components()
		self.assertIn("Dialog", builder.components)
		self.assertIn("TextInput", builder.components)

	def test_handles_string_slot_content(self):
		"""String slot content should be gracefully skipped without errors."""
		app = make_studio_app(app_title="Str Slot App", app_name="str-slot-app")
		blocks = json.dumps(
			[
				{
					"componentName": "Tooltip",
					"children": [],
					"componentSlots": {"default": {"slotContent": "Some plain text"}},
				}
			]
		)
		make_studio_page(app.name, page_title="Str Slot Page", blocks=blocks, published=1)

		builder = StudioAppBuilder(app.name, is_standard=False)
		builder.get_app_components()
		self.assertIn("Tooltip", builder.components)

	def test_extracts_h_function_components(self):
		"""h(ComponentName, ...) calls in blocks string should be extracted."""
		app = make_studio_app(app_title="H Func App", app_name="h-func-app")
		blocks = json.dumps(
			[
				{
					"componentName": "div",
					"children": [],
					"render": 'h(Alert, {}, [h(Button, { label: "OK" }), h(Badge, { text: "New" })])',
				}
			]
		)
		make_studio_page(app.name, page_title="H Func Page", blocks=blocks, published=1)

		builder = StudioAppBuilder(app.name, is_standard=False)
		builder.get_app_components()
		self.assertIn("Alert", builder.components)
		self.assertIn("Button", builder.components)
		self.assertIn("Badge", builder.components)

	def test_extracts_components_from_multiple_pages(self):
		app = make_studio_app(app_title="Multi Page App", app_name="multi-page-app")
		blocks_1 = json.dumps([{"componentName": "Alert", "children": []}])
		blocks_2 = json.dumps([{"componentName": "Avatar", "children": []}])
		make_studio_page(app.name, page_title="Page One", route="/page-one", blocks=blocks_1, published=1)
		make_studio_page(app.name, page_title="Page Two", route="/page-two", blocks=blocks_2, published=1)

		builder = StudioAppBuilder(app.name, is_standard=False)
		builder.get_app_components()
		self.assertIn("Alert", builder.components)
		self.assertIn("Avatar", builder.components)

	def test_ignores_unpublished_pages(self):
		app = make_studio_app(app_title="Unpub Pages App", app_name="unpub-pages-app")
		blocks = json.dumps([{"componentName": "Calendar", "children": []}])
		make_studio_page(app.name, page_title="Draft Page", blocks=blocks, published=0)

		builder = StudioAppBuilder(app.name, is_standard=False)
		result = builder.get_app_components()
		self.assertNotIn("Calendar", builder.components)
		self.assertEqual(result, set())

	def test_get_published_custom_apps(self):
		app = make_studio_app(app_title="Published Custom", app_name="published-custom")
		blocks = json.dumps([{"componentName": "Alert", "children": []}])
		make_studio_page(app.name, page_title="Pub Page", blocks=blocks, published=1)

		unpublished_app = make_studio_app(app_title="Unpublished Custom", app_name="unpublished-custom")
		make_studio_page(unpublished_app.name, page_title="Unp Page", published=0)

		standard_app = make_studio_app(
			app_title="Standard Excluded",
			app_name="standard-excluded",
			is_standard=1,
			frappe_app="studio",
		)
		blocks = json.dumps([{"componentName": "Alert", "children": []}])
		make_studio_page(standard_app.name, page_title="Std Page", blocks=blocks, published=1)

		result = get_published_custom_apps()
		self.assertIn(app.name, result)
		self.assertNotIn(unpublished_app.name, result)
		self.assertNotIn(standard_app.name, result)

	def test_get_app_components_from_files(self):
		"""Create temp JSON files mimicking an exported app and verify component extraction."""
		app_name = "file-test-app"
		page_data = {
			"blocks": [
				{
					"componentName": "TextEditor",
					"children": [{"componentName": "Dropdown", "children": []}],
				}
			]
		}

		with mock_studio_app_files(app_name, pages={"my_page": page_data}) as studio_folder:
			builder = StudioAppBuilder(app_name, is_standard=True, frappe_app="studio")
			with patch("studio.build.get_studio_folder", return_value=studio_folder):
				builder.get_app_components_from_files()

			self.assertIn("TextEditor", builder.components)
			self.assertIn("Dropdown", builder.components)

	def test_get_app_components_from_files_with_string_blocks(self):
		"""Blocks stored as a JSON string (instead of list) should also be parsed."""
		app_name = "str-blocks-app"
		blocks = [{"componentName": "Alert", "children": []}]
		page_data = {"blocks": json.dumps(blocks)}

		with mock_studio_app_files(app_name, pages={"page": page_data}) as studio_folder:
			builder = StudioAppBuilder(app_name, is_standard=True, frappe_app="studio")
			with patch("studio.build.get_studio_folder", return_value=studio_folder):
				builder.get_app_components_from_files()

			self.assertIn("Alert", builder.components)

	def test_get_app_components_from_files_with_studio_components(self):
		"""Studio components referenced in pages should be recursively resolved from disk."""
		app_name = "studio-comp-app"
		page_data = {"blocks": [{"componentName": "MyWidget", "isStudioComponent": True, "children": []}]}
		comp_data = {
			"name": "MyWidget",
			"block": {"componentName": "Alert", "children": [{"componentName": "Badge", "children": []}]},
		}

		with mock_studio_app_files(
			app_name, pages={"page": page_data}, components={"my_widget": comp_data}
		) as studio_folder:
			builder = StudioAppBuilder(app_name, is_standard=True, frappe_app="studio")
			with patch("studio.build.get_studio_folder", return_value=studio_folder):
				builder.get_app_components_from_files()

			self.assertIn("Alert", builder.components)
			self.assertIn("Badge", builder.components)

	def test_build_paths_for_standard_app(self):
		app_name = "standard-app"
		builder = StudioAppBuilder(app_name, is_standard=True, frappe_app="studio")

		self.assertIn("public/app_builds", builder.out_dir)
		self.assertEqual(builder.base, f"/assets/studio/app_builds/{app_name}/")

	def test_build_paths_for_custom_app(self):
		app_name = "custom-app"
		builder = StudioAppBuilder(app_name, is_standard=False)

		expected_files_path = os.path.abspath(get_files_path("app_builds", app_name))
		self.assertEqual(builder.out_dir, expected_files_path)
		self.assertEqual(builder.base, f"/files/app_builds/{app_name}/")


def make_studio_app(**kwargs):
	app = frappe.new_doc("Studio App")
	app.update(
		{
			"app_title": kwargs.get("app_title", "Test App"),
			"app_name": kwargs.get("app_name", "test-app"),
			"is_standard": kwargs.get("is_standard", 0),
			"frappe_app": kwargs.get("frappe_app", ""),
		}
	)
	if "route" in kwargs:
		app.route = kwargs.get("route")
	app.insert()
	return app


def make_studio_page(studio_app, **kwargs):
	page = frappe.new_doc("Studio Page")
	page.update(
		{
			"studio_app": studio_app,
			"page_title": kwargs.get("page_title", "Test Page"),
			"route": kwargs.get("route", "/test-page"),
			"blocks": kwargs.get("blocks", "[]"),
			"published": kwargs.get("published", 1),
		}
	)
	page.insert()
	return page


@contextmanager
def mock_studio_app_files(app_name, pages=None, components=None):
	tmpdir = tempfile.mkdtemp()
	try:
		studio_folder = os.path.join(tmpdir, "studio")
		app_folder = os.path.join(studio_folder, app_name)
		page_folder = os.path.join(app_folder, "studio_page")
		os.makedirs(page_folder)

		if pages:
			# each page is exported into its own folder holding <stem>.json (+ optional <stem>.ts)
			for page_name, page_data in pages.items():
				page_dir = os.path.join(page_folder, page_name)
				os.makedirs(page_dir, exist_ok=True)
				with open(os.path.join(page_dir, f"{page_name}.json"), "w") as f:
					json.dump(page_data, f)

		if components:
			comp_folder = os.path.join(app_folder, "studio_components")
			os.makedirs(comp_folder)
			for comp_name, comp_data in components.items():
				with open(os.path.join(comp_folder, f"{comp_name}.json"), "w") as f:
					json.dump(comp_data, f)

		yield studio_folder
	finally:
		shutil.rmtree(tmpdir)
