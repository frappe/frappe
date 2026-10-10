# Copyright (c) 2024, Frappe Technologies Pvt Ltd and Contributors
# See license.txt

import json
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_files_path

from studio.build import StudioAppBuilder, get_published_custom_apps, get_router_file
from studio.studio.doctype.studio_app.studio_app import StudioApp


class TestStudioApp(FrappeTestCase):
	def test_studio_app_creation(self):
		app = make_studio_app(app_title="My Build App", app_name="my-build-app")
		self.assertEqual(app.app_title, "My Build App")
		self.assertEqual(app.route, "my-build-app")

	def test_export_router_script(self):
		with exports_in_tempdir():
			app = make_studio_app(app_title="Routed Custom App", app_name="routed-custom-app")
			app.router_script = ROUTER_SCRIPT
			app.save()
			context = get_renderer_context(app)
			self.assertEqual(context.router_script, ROUTER_SCRIPT)
			self.assertIsNone(context.router_file)

			app.enable_app_export("studio")
			app.reload()
			self.assertFalse(app.router_script)
			self.assertEqual(
				frappe.read_file(app.get_router_file_path()),
				f"export default {ROUTER_SCRIPT}\n",
			)
			app.router_script = ROUTER_SCRIPT
			context = get_renderer_context(app)
			self.assertEqual(context.router_file, app.get_router_file_path())
			self.assertIsNone(context.router_script)
			with patch.dict(frappe.conf, {"developer_mode": 0}):
				self.assertIsNone(get_renderer_context(app).router_file)
			app.router_script = None
			exported = json.loads(
				frappe.read_file(os.path.join(app.get_folder_path(), "routed_custom_app.json"))
			)
			self.assertNotIn("router_script", exported)

			app.disable_app_export()
			self.assertEqual(app.reload().router_script, ROUTER_SCRIPT)

	def test_app_favicon(self):
		app = make_studio_app(app_title="Favicon App", app_name="favicon-app")
		self.assertIn('href="/assets/studio/frontend/favicon.png"', render_app_template(app))

		app.favicon = "/files/favicon-app.png"
		self.assertIn('href="/files/favicon-app.png"', render_app_template(app))

	def test_rename_keeps_exported_files(self):
		with exports_in_tempdir():
			app, page = make_exported_app_with_files("rename-me")
			old_folder = app.get_folder_path()

			frappe.rename_doc("Studio App", app.name, "renamed-app")

			app = frappe.get_doc("Studio App", "renamed-app")
			page.reload()
			self.assertEqual(app.app_name, "renamed-app")
			self.assertFalse(os.path.exists(old_folder))
			self.assert_exported_files_kept(app, page)
			self.assertTrue(os.path.exists(os.path.join(app.get_folder_path(), "renamed_app.json")))
			self.assertFalse(os.path.exists(os.path.join(app.get_folder_path(), "rename_me.json")))
			exported_page = json.loads(frappe.read_file(page.get_folder_path(with_filename=True)))
			self.assertEqual(exported_page["studio_app"], "renamed-app")

	def test_changing_the_frappe_app_moves_the_export_folder(self):
		with exports_in_tempdir():
			app, page = make_exported_app_with_files("moving-app")
			old_folder = app.get_folder_path()

			app.enable_app_export("frappe")

			page.reload()
			self.assertFalse(os.path.exists(old_folder))
			self.assert_exported_files_kept(app, page)

	def assert_exported_files_kept(self, app, page):
		self.assertEqual(frappe.read_file(app.get_router_file_path()), f"export default {ROUTER_SCRIPT}\n")
		self.assertEqual(frappe.read_file(page.get_script_file_path()), "console.log('kept')")
		extra_file = os.path.join(app.get_folder_path(), "Extra.vue")
		self.assertEqual(frappe.read_file(extra_file), "<template>kept</template>")

	def test_rename_keeps_the_app_json_when_the_names_scrub_the_same(self):
		with exports_in_tempdir():
			app = make_studio_app(app_title="Dashed App", app_name="dashed-app")
			app.enable_app_export("studio")

			frappe.rename_doc("Studio App", app.name, "dashed_app")

			app = frappe.get_doc("Studio App", "dashed_app")
			self.assertTrue(os.path.exists(os.path.join(app.get_folder_path(), "dashed_app.json")))
			StudioApp.remove_from_studio_apps_txt.assert_not_called()

	def test_exported_apps_cannot_be_renamed_outside_developer_mode(self):
		app = make_studio_app(app_title="Deployed App", app_name="deployed-app")
		app.db_set({"is_standard": 1, "frappe_app": "studio"})
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			self.assertRaises(frappe.ValidationError, frappe.rename_doc, "Studio App", app.name, "deployed-renamed")

	def test_validate_app_name(self):
		app = make_studio_app(app_title="Valid App", app_name="valid-app")
		for name in ("Has Space", "UPPER", "a/b"):
			self.assertRaises(frappe.ValidationError, make_studio_app, app_title="Invalid", app_name=name)
			self.assertRaises(frappe.ValidationError, frappe.rename_doc, "Studio App", app.name, name)

		self.assertEqual(make_studio_app(app_title="Café (v2)!", app_name=None).name, "café-v2")

	def test_studio_app_boot(self):
		app = unsaved_studio_app("boot-app")
		with patch_boot_hook(app.name, f"{__name__}.boot_contribution"):
			self.assertEqual(app.get_boot(), {"roles": ["Customer"]})

	def test_boot_drops_a_failing_contributor(self):
		app = unsaved_studio_app("broken-boot-app")
		with patch_boot_hook(app.name, f"{__name__}.failing_contribution"), patch(
			"frappe.log_error"
		) as log_error:
			self.assertEqual(app.get_boot(), {})
		log_error.assert_called_once_with(title=f"studio_app_boot failed for {app.name}")


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

	def test_skips_native_html_elements(self):
		app = make_studio_app(app_title="Native Element App", app_name="native-element-app")
		blocks = json.dumps(
			[
				{
					"componentName": "TextInput",
					"children": [],
					"componentSlots": {
						"prefix": {
							"slotContent": [
								{
									"componentName": "span",
									"originalElement": "span",
									"classes": ["lucide-search"],
								},
							]
						}
					},
				}
			]
		)
		make_studio_page(app.name, page_title="Native Element Page", blocks=blocks, published=1)

		builder = StudioAppBuilder(app.name, is_standard=False)
		builder.get_app_components()
		self.assertEqual(builder.components, {"TextInput"})

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

	def test_collects_icons_from_pages_scripts_and_components(self):
		app = make_studio_app(app_title="Icon App", app_name="icon-app")
		component = frappe.get_doc(
			{
				"doctype": "Studio Component",
				"component_name": "IconWidget",
				"block": json.dumps({"componentName": "Button", "componentProps": {"icon": "lucide-star"}}),
			}
		).insert()
		blocks = json.dumps(
			[
				{
					"componentName": "Button",
					"componentProps": {"iconLeft": "lucide-plus", "class": "hover:lucide-arrow-up-right"},
					"children": [
						{"componentName": component.name, "isStudioComponent": True, "children": []}
					],
				}
			]
		)
		make_studio_page(
			app.name, blocks=blocks, script="const icon = ok ? 'lucide-check' : 'lucide-x'", published=1
		)

		builder = StudioAppBuilder(app.name, is_standard=False)
		builder.get_app_components()
		self.assertEqual(
			builder.icons, {"lucide-plus", "lucide-arrow-up-right", "lucide-star", "lucide-check", "lucide-x"}
		)

	def test_collects_icons_from_files(self):
		app_name = "icon-file-app"
		page_data = {
			"blocks": [
				{
					"componentName": "Button",
					"componentProps": {"icon": "lucide-house"},
					"children": [{"componentName": "FileWidget", "isStudioComponent": True, "children": []}],
				}
			]
		}
		comp_data = {
			"name": "FileWidget",
			"block": {"componentName": "Icon", "componentProps": {"icon": "lucide-bell"}},
		}

		with mock_studio_app_files(
			app_name, pages={"page": page_data}, components={"file_widget": comp_data}
		) as studio_folder:
			builder = StudioAppBuilder(app_name, is_standard=True, frappe_app="studio")
			with patch("studio.build.get_studio_folder", return_value=studio_folder):
				builder.get_app_components_from_files()

		self.assertEqual(builder.icons, {"lucide-house", "lucide-bell"})

	def test_passes_only_the_used_icons_to_the_build(self):
		builder = StudioAppBuilder("icon-cli-app", is_standard=False)
		builder.components = {"Button"}
		builder.icons = {"lucide-x", "lucide-check"}

		with patch("studio.build.subprocess.run") as run, patch("studio.build.os.makedirs"):
			run.return_value.returncode = 0
			builder._run_vite_build()
		self.assertIn(" --icons lucide-check,lucide-x", run.call_args.args[0])

		builder.icons = set()
		with patch("studio.build.subprocess.run") as run, patch("studio.build.os.makedirs"):
			run.return_value.returncode = 0
			builder._run_vite_build()
		self.assertNotIn("--icons", run.call_args.args[0])

	def test_passes_the_router_file_to_the_build(self):
		builder = StudioAppBuilder("routed-app", is_standard=True, frappe_app="studio")
		builder.components = {"Button"}
		with mock_studio_app_files("routed-app", router="{}") as studio_folder, patch(
			"studio.build.get_studio_folder", return_value=studio_folder
		):
			self.assertEqual(
				get_router_file("studio", "routed-app"),
				os.path.join(studio_folder, "routed_app", "router.ts"),
			)
			builder.router_file = get_router_file("studio", "routed-app")
			with patch("studio.build.subprocess.run") as run, patch("studio.build.os.makedirs"):
				run.return_value.returncode = 0
				builder._run_vite_build()
			self.assertIn(f" --router-file {builder.router_file}", run.call_args.args[0])

		# a bench path with spaces must reach vite as one argument
		builder.router_file = "/Users/me/my bench/apps/studio/studio/routed_app/router.ts"
		with patch("studio.build.subprocess.run") as run, patch("studio.build.os.makedirs"):
			run.return_value.returncode = 0
			builder._run_vite_build()
		self.assertIn(
			" --router-file '/Users/me/my bench/apps/studio/studio/routed_app/router.ts'",
			run.call_args.args[0],
		)

		with mock_studio_app_files("routed-app") as studio_folder, patch(
			"studio.build.get_studio_folder", return_value=studio_folder
		):
			self.assertIsNone(get_router_file("studio", "routed-app"))

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

	def test_build_resolves_framework_ui(self):
		"""A bench never installs frappe/ui/node_modules, so @framework/ui's own dependencies
		(marked, leaflet, …) must resolve from Studio's node_modules in app builds."""
		framework_ui_package = os.path.join(frappe.get_app_source_path("frappe"), "ui", "package.json")
		if not os.path.exists(framework_ui_package):
			self.skipTest("@framework/ui is not available on this frappe version")

		app = make_studio_app(app_title="Framework UI App", app_name="framework-ui-app")
		blocks = json.dumps([{"componentName": "FormLayout", "children": []}])
		make_studio_page(app.name, page_title="Form Page", blocks=blocks, published=1)

		builder = StudioAppBuilder(app.name, is_standard=False)
		builder.out_dir = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, builder.out_dir)
		builder.build()

		with open(framework_ui_package) as f:
			dependencies = json.load(f)["dependencies"]
		bundled = get_bundled_packages(builder.out_dir)
		self.assertTrue(bundled & dependencies.keys(), f"no @framework/ui dependency in {bundled}")


ROUTER_SCRIPT = """{
	extendRoute(route) {
		if (route.name === "Board") route.alias = "/tasks"
	},
}"""


@contextmanager
def exports_in_tempdir():
	with (
		tempfile.TemporaryDirectory() as tmpdir,
		# scrubbed like the real one, so `routed-app` resolves to `routed_app` everywhere
		patch(
			"frappe.get_app_source_path",
			side_effect=lambda app, *path: os.path.join(tmpdir, app, *map(frappe.scrub, path)),
		),
		patch.dict(frappe.conf, {"developer_mode": 1}),
		patch.object(StudioApp, "add_to_studio_apps_txt"),
		patch.object(StudioApp, "remove_from_studio_apps_txt"),
	):
		yield


def get_renderer_context(app):
	context = frappe._dict()
	# get_context commits for the csrf token, which would leak the app past the test rollback
	with patch.object(frappe.db, "commit"):
		app.get_context(context)
	return context


def make_exported_app_with_files(app_name):
	"""An app exported to studio with a page script, router.ts and a file only the folder has."""
	app = make_studio_app(app_title=app_name.title(), app_name=app_name)
	page = make_studio_page(app.name, page_title=f"{app.app_title} Page", script="console.log('kept')")
	app.reload()  # the first page becomes the app home
	app.router_script = ROUTER_SCRIPT
	app.save()
	app.enable_app_export("studio")
	with open(os.path.join(app.get_folder_path(), "Extra.vue"), "w") as f:
		f.write("<template>kept</template>")
	return app, page


def render_app_template(app):
	return frappe.render_template(StudioApp.website.template, get_renderer_context(app))


def unsaved_studio_app(name):
	app = frappe.new_doc("Studio App")
	app.name = name
	return app


def boot_contribution():
	return {"roles": ["Customer"]}


def failing_contribution():
	raise ValueError("no boot for you")


@contextmanager
def patch_boot_hook(app_name, handler):
	get_hooks = frappe.get_hooks

	def with_boot_hook(hook=None, *args, **kwargs):
		if hook == "studio_app_boot":
			return {app_name: [handler]}
		return get_hooks(hook, *args, **kwargs)

	with patch("frappe.get_hooks", side_effect=with_boot_hook):
		yield


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
			"script": kwargs.get("script"),
			"published": kwargs.get("published", 1),
			"allow_guest": kwargs.get("allow_guest", 0),
		}
	)
	page.insert()
	return page


def get_bundled_packages(out_dir: str) -> set[str]:
	"""Names of node_modules packages listed as sources in the build's sourcemaps."""
	packages = set()
	assets_dir = os.path.join(out_dir, "assets")
	for file_name in os.listdir(assets_dir):
		if not file_name.endswith(".js.map"):
			continue
		with open(os.path.join(assets_dir, file_name)) as f:
			sources = json.load(f)["sources"]
		for source in sources:
			packages.update(re.findall(r"node_modules/((?:@[^/]+/)?[^/]+)/", source))
	return packages


@contextmanager
def mock_studio_app_files(app_name, pages=None, components=None, router=None):
	tmpdir = tempfile.mkdtemp()
	try:
		studio_folder = os.path.join(tmpdir, "studio")
		app_folder = os.path.join(studio_folder, frappe.scrub(app_name))
		page_folder = os.path.join(app_folder, "studio_page")
		os.makedirs(page_folder)

		if router is not None:
			with open(os.path.join(app_folder, "router.ts"), "w") as f:
				f.write(router)

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
