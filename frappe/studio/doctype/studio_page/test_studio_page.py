# Copyright (c) 2024, Frappe Technologies Pvt Ltd and Contributors
# See license.txt

import os
import tempfile
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from studio.studio.doctype.studio_app.studio_app import StudioApp, StudioAppRenderer
from studio.studio.doctype.studio_app.test_studio_app import make_studio_app, make_studio_page
from studio.studio.doctype.studio_page import copy_paste
from studio.studio.doctype.studio_page.studio_page import (
	create_missing_dependencies,
	duplicate_page,
	get_page,
	paste_page,
)

PAGE_SCRIPT = "export function setup() { return { greeting: 'hi' } }"
TODO_RESOURCE = {
	"resource_type": "Document List",
	"resource_name": "todos",
	"document_type": "ToDo",
	"fields": '["name"]',
}


def make_component(component_name: str, block: dict | None = None, inputs: list[dict] | None = None):
	component = frappe.new_doc("Studio Component")
	component.component_name = component_name
	component.block = frappe.as_json(block or {"componentName": "div", "children": []}, indent=None)
	for input_row in inputs or []:
		component.append("inputs", input_row)
	component.insert()
	return component


def component_ref(component) -> dict:
	return {"componentName": component.name, "isStudioComponent": True, "children": []}


def make_page_with_data(app_name: str):
	page = make_studio_page(app_name, page_title="Board", route="/board", published=0)
	page.append("resources", TODO_RESOURCE)
	page.append("variables", {"variable_name": "count", "variable_type": "Number"})
	page.script = PAGE_SCRIPT
	page.save()
	return page


@contextmanager
def exports_in_tempdir():
	with (
		tempfile.TemporaryDirectory() as tmpdir,
		patch("frappe.get_app_source_path", side_effect=lambda app, *path: os.path.join(tmpdir, app, *path)),
		patch.dict(frappe.conf, {"developer_mode": 1}),
		patch.object(StudioApp, "add_to_studio_apps_txt"),
	):
		yield


class TestStudioPage(IntegrationTestCase):
	BLOCKS = [{"componentName": "div", "children": [{"componentName": "span"}]}]

	def test_block_parsing(self):
		app = make_studio_app(app_name="serialization-" + frappe.generate_hash(length=10))
		blocks = [{"componentName": "div", "children": [{"componentName": "span"}]}]
		page = frappe.get_doc(
			doctype="Studio Page", studio_app=app.name, blocks=blocks, draft_blocks=blocks
		).insert()
		page.reload()
		self.assertEqual(page.blocks, frappe.as_json(blocks, indent=None))
		self.assertEqual(frappe.parse_json(page.blocks), blocks)
		self.assertEqual(frappe.parse_json(page.draft_blocks), blocks)

	def test_duplicate_page(self):
		app = make_studio_app(app_name="dup-" + frappe.generate_hash(length=10))
		page = make_page_with_data(app.name)

		copy = duplicate_page(page.name, app.name)

		self.assertEqual(copy.page_title, "Board Copy")
		self.assertNotEqual(copy.route, page.route)
		self.assertFalse(copy.published)
		self.assertEqual([r.resource_name for r in copy.resources], ["todos"])
		self.assertEqual([v.variable_name for v in copy.variables], ["count"])
		self.assertEqual(copy.script, PAGE_SCRIPT)

		second_copy = duplicate_page(page.name, app.name)
		self.assertEqual(second_copy.page_title, "Board Copy 1")

	def test_paste_replaces_page_contents_but_keeps_its_identity(self):
		app = make_studio_app(app_name="paste-" + frappe.generate_hash(length=10))
		source = make_page_with_data(app.name)
		target = make_studio_page(app.name, page_title="Target", route="/target")

		paste_page(app.name, {**source.get_copy(), "blocks": self.BLOCKS}, target_page=target.name)

		target.reload()
		self.assertEqual(target.page_title, "Target")
		self.assertEqual(target.route, "/target")
		self.assertEqual(frappe.parse_json(target.draft_blocks), self.BLOCKS)
		self.assertEqual([r.resource_name for r in target.resources], ["todos"])
		self.assertEqual(target.script, PAGE_SCRIPT)

	def test_paste_creates_missing_components(self):
		app = make_studio_app(app_name="paste-" + frappe.generate_hash(length=10))
		component = make_component("Card", inputs=[{"input_name": "title", "type": "String"}])
		blocks = [{"componentName": "div", "children": [component_ref(component)]}]
		copy = {**make_studio_page(app.name).get_copy(blocks), "blocks": blocks}
		self.assertEqual([c["name"] for c in copy["components"]], [component.name])
		frappe.delete_doc("Studio Component", component.name)

		paste_page(app.name, copy)

		pasted = frappe.get_doc("Studio Component", component.name)
		self.assertEqual(pasted.component_name, "Card")
		self.assertEqual(pasted.block, component.block)
		self.assertEqual([i.input_name for i in pasted.inputs], ["title"])
		result = create_missing_dependencies(app.name, copy["components"])
		self.assertEqual(result["conflicts"]["components"], [])

	def test_paste_reports_conflicting_component(self):
		app = make_studio_app(app_name="conflict-" + frappe.generate_hash(length=10))
		component = make_component("Card")
		copy = make_studio_page(app.name).get_dependencies([component_ref(component)])["components"][0]
		copy["block"] = frappe.as_json({"componentName": "button", "children": []}, indent=None)

		result = create_missing_dependencies(app.name, [copy])

		component.reload()
		self.assertEqual(frappe.parse_json(component.block)["componentName"], "div")
		conflict = result["conflicts"]["components"][0]
		self.assertEqual(conflict["name"], "Card")
		self.assertEqual(frappe.parse_json(conflict["existing"]["block"])["componentName"], "div")
		self.assertEqual(frappe.parse_json(conflict["copied"]["block"])["componentName"], "button")

		create_missing_dependencies(app.name, [copy], overwrite_conflicts=True)
		component.reload()
		self.assertEqual(frappe.parse_json(component.block)["componentName"], "button")

		create_missing_dependencies(app.name, [conflict["existing"]], overwrite_conflicts=True)
		component.reload()
		self.assertEqual(frappe.parse_json(component.block)["componentName"], "div")

	def test_concurrent_component_creation_reuses_component(self):
		app = make_studio_app(app_name="race-" + frappe.generate_hash(length=10))
		component = make_component("Card")
		copy = make_studio_page(app.name).get_dependencies([component_ref(component)])["components"][0]
		real_fetch_component_batch = copy_paste.fetch_component_batch
		missed_once = False

		def miss_component_once(names, **kwargs):
			nonlocal missed_once
			if component.name in names and not missed_once:
				missed_once = True
				return []
			return real_fetch_component_batch(names, **kwargs)

		with patch.object(copy_paste, "fetch_component_batch", side_effect=miss_component_once):
			create_missing_dependencies(app.name, [copy])

		self.assertTrue(missed_once)
		self.assertEqual(frappe.db.count("Studio Component", {"name": component.name}), 1)

	def test_existing_components_do_not_use_per_component_exists_queries(self):
		app = make_studio_app(app_name="batch-" + frappe.generate_hash(length=10))
		components = [make_component("Card"), make_component("Button")]
		copies = make_studio_page(app.name).get_dependencies(
			[component_ref(component) for component in components]
		)["components"]

		with patch.object(frappe.db, "exists", side_effect=AssertionError("unexpected exists query")):
			result = create_missing_dependencies(app.name, copies)

		self.assertEqual(result["conflicts"]["components"], [])

	def test_paste_requires_write_permission_on_target_app(self):
		app = make_studio_app(app_name="permission-" + frappe.generate_hash(length=10))

		with (
			patch.object(StudioApp, "check_permission", side_effect=frappe.PermissionError),
			self.assertRaises(frappe.PermissionError),
		):
			create_missing_dependencies(app.name)

	def test_paste_carries_files_the_script_imports(self):
		with exports_in_tempdir():
			source_app = make_studio_app(
				app_name="src-" + frappe.generate_hash(length=10), is_standard=1, frappe_app="studio"
			)
			target_app = make_studio_app(
				app_name="dst-" + frappe.generate_hash(length=10), is_standard=1, frappe_app="studio"
			)
			page = make_studio_page(source_app.name)
			page.get_app().write_files([{"path": "stores/settings.ts", "content": "export const x = 1"}])
			page.script = 'import { x } from "@app/stores/settings"\nexport default function setup() {}'
			page.save()

			copy = page.get_copy()
			self.assertEqual([f["path"] for f in copy["files"]], ["stores/settings.ts"])

			pasted = paste_page(target_app.name, {**copy, "blocks": []})

			self.assertEqual(
				frappe.read_file(os.path.join(pasted.get_app().get_folder_path(), "stores/settings.ts")),
				"export const x = 1",
			)

	def test_paste_rejects_conflicting_files_before_writing(self):
		with exports_in_tempdir():
			app = make_studio_app(
				app_name="files-" + frappe.generate_hash(length=10), is_standard=1, frappe_app="studio"
			)
			app.write_files([{"path": "stores/settings.ts", "content": "export const x = 1"}])

			with self.assertRaisesRegex(frappe.ValidationError, "different content"):
				app.write_files(
					[
						{"path": "stores/new.ts", "content": "export const y = 1"},
						{"path": "stores/settings.ts", "content": "export const x = 2"},
					]
				)

			self.assertFalse(os.path.exists(os.path.join(app.get_folder_path(), "stores/new.ts")))
			self.assertEqual(
				frappe.read_file(os.path.join(app.get_folder_path(), "stores/settings.ts")),
				"export const x = 1",
			)

	def test_copy_rejects_ambiguous_custom_component(self):
		with exports_in_tempdir():
			app = make_studio_app(
				app_name="files-" + frappe.generate_hash(length=10), is_standard=1, frappe_app="studio"
			)
			app.write_files(
				[
					{"path": "components/Hero.vue", "content": "<template><h1 /></template>"},
					{"path": "views/Hero.vue", "content": "<template><h2 /></template>"},
				]
			)

			with self.assertRaisesRegex(frappe.ValidationError, "ambiguous"):
				app.find_vue_component("Hero")

	def test_copy_does_not_follow_file_links_outside_the_app(self):
		with exports_in_tempdir():
			app = make_studio_app(
				app_name="files-" + frappe.generate_hash(length=10), is_standard=1, frappe_app="studio"
			)
			outside = os.path.join(os.path.dirname(app.get_folder_path()), "secret.ts")
			with open(outside, "w") as f:
				f.write("export const secret = true")
			os.makedirs(os.path.join(app.get_folder_path(), "stores"))
			os.symlink(outside, os.path.join(app.get_folder_path(), "stores/secret.ts"))

			with self.assertRaises(frappe.PermissionError):
				app.collect_files('import "@app/stores/secret.ts"', "", [])

	def test_pasted_blocks_install_their_dependencies(self):
		with exports_in_tempdir():
			app = make_studio_app(
				app_name="deps-" + frappe.generate_hash(length=10), is_standard=1, frappe_app="studio"
			)
			component = make_component("Card")
			blocks = [component_ref(component), {"componentName": "Hero", "isCustomVueComponent": True}]
			app.write_files([{"path": "components/Hero.vue", "content": "<template><h1 /></template>"}])
			deps = make_studio_page(app.name).get_dependencies(blocks)
			self.assertEqual([c["name"] for c in deps["components"]], [component.name])
			self.assertEqual([f["path"] for f in deps["files"]], ["components/Hero.vue"])

			frappe.delete_doc("Studio Component", component.name)
			os.remove(os.path.join(app.get_folder_path(), "components/Hero.vue"))
			create_missing_dependencies(app.name, deps["components"], deps["files"])
			create_missing_dependencies(app.name, deps["components"], deps["files"])

			self.assertTrue(frappe.db.exists("Studio Component", component.name))
			self.assertTrue(os.path.exists(os.path.join(app.get_folder_path(), "components/Hero.vue")))

	def test_pasted_blocks_bring_the_data_sources_and_variables_they_use(self):
		app = make_studio_app(app_name="deps-" + frappe.generate_hash(length=10))
		source = make_page_with_data(app.name)
		target = make_studio_page(app.name, page_title="Target", route="/target")
		blocks = [{"componentName": "div", "innerHTML": "{{ todos.data.length }} / {{ count }}"}]

		deps = source.get_dependencies(blocks)
		self.assertEqual([r["resource_name"] for r in deps["resources"]], ["todos"])
		self.assertEqual([v["variable_name"] for v in deps["variables"]], ["count"])

		first_result = create_missing_dependencies(
			app.name, page_name=target.name, resources=deps["resources"], variables=deps["variables"]
		)
		equivalent_resources = [{**deps["resources"][0], "fields": ["name"]}]
		second_result = create_missing_dependencies(
			app.name, page_name=target.name, resources=equivalent_resources, variables=deps["variables"]
		)

		target.reload()
		self.assertEqual([r.resource_name for r in target.resources], ["todos"])
		self.assertEqual([v.variable_name for v in target.variables], ["count"])
		no_conflicts = {"components": [], "resources": [], "variables": []}
		self.assertEqual(first_result["conflicts"], no_conflicts)
		self.assertEqual(second_result["conflicts"], no_conflicts)

	def test_pasted_blocks_report_conflicting_page_data(self):
		app = make_studio_app(app_name="deps-" + frappe.generate_hash(length=10))
		source = make_page_with_data(app.name)
		target = make_studio_page(app.name, page_title="Target", route="/target")
		target.append("resources", {**TODO_RESOURCE, "fields": '["description"]'})
		target.append(
			"variables", {"variable_name": "count", "variable_type": "String", "initial_value": "zero"}
		)
		target.save()
		dependencies = source.get_dependencies([{"innerHTML": "{{ todos.data }} {{ count }}"}])

		result = create_missing_dependencies(
			app.name,
			page_name=target.name,
			resources=dependencies["resources"],
			variables=dependencies["variables"],
		)

		target.reload()
		self.assertEqual(len(target.resources), 1)
		self.assertEqual(target.resources[0].fields, '["description"]')
		self.assertEqual(len(target.variables), 1)
		self.assertEqual(target.variables[0].variable_type, "String")
		resource_conflict = result["conflicts"]["resources"][0]
		variable_conflict = result["conflicts"]["variables"][0]
		self.assertEqual(resource_conflict["name"], "todos")
		self.assertEqual(resource_conflict["existing"]["fields"], '["description"]')
		self.assertEqual(resource_conflict["copied"]["fields"], '["name"]')
		self.assertEqual(variable_conflict["name"], "count")
		self.assertEqual(variable_conflict["existing"]["variable_type"], "String")
		self.assertEqual(variable_conflict["copied"]["variable_type"], "Number")

		create_missing_dependencies(
			app.name,
			page_name=target.name,
			resources=dependencies["resources"],
			overwrite_conflicts=True,
		)
		target.reload()
		self.assertEqual(target.resources[0].fields, '["name"]')
		self.assertEqual(target.variables[0].variable_type, "String")

		create_missing_dependencies(
			app.name,
			page_name=target.name,
			variables=dependencies["variables"],
			overwrite_conflicts=True,
		)
		target.reload()
		self.assertEqual(target.variables[0].variable_type, "Number")

		create_missing_dependencies(
			app.name,
			page_name=target.name,
			resources=[resource_conflict["existing"]],
			variables=[variable_conflict["existing"]],
			overwrite_conflicts=True,
		)
		target.reload()
		self.assertEqual(target.resources[0].fields, '["description"]')
		self.assertEqual(target.variables[0].variable_type, "String")

	def test_paste_rejects_target_page_from_another_app(self):
		app = make_studio_app(app_name="target-" + frappe.generate_hash(length=10))
		other_app = make_studio_app(app_name="other-" + frappe.generate_hash(length=10))
		target = make_studio_page(other_app.name)

		with self.assertRaisesRegex(frappe.PermissionError, "does not belong"):
			paste_page(app.name, {"blocks": []}, target_page=target.name)

	def test_standard_page_script_is_copied_as_file(self):
		with exports_in_tempdir():
			app = make_studio_app(app_name="dup-" + frappe.generate_hash(length=10))
			page = make_page_with_data(app.name)
			app.reload()
			app.enable_app_export("studio")
			page.reload()
			self.assertFalse(page.script)

			copy = duplicate_page(page.name, app.name)

			self.assertTrue(copy.is_standard)
			self.assertFalse(copy.script)
			self.assertEqual(frappe.read_file(copy.get_script_file_path()), PAGE_SCRIPT)


class TestGuestRendering(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.delete_leftover_fixtures()
		cls.app = make_studio_app(app_title="Guest Test App", app_name="guest-test-app")
		cls.nested_card = make_component("Nested Card")
		cls.hero = make_component(
			"Hero Section",
			block={"componentName": "div", "children": [component_ref(cls.nested_card)]},
			inputs=[{"input_name": "title", "type": "String"}],
		)
		cls.secret_widget = make_component("Secret Widget")
		cls.public_page = make_studio_page(
			cls.app.name,
			page_title="Public Page",
			route="/public",
			allow_guest=1,
			blocks=frappe.as_json([{"componentName": "div", "children": [component_ref(cls.hero)]}]),
		)
		cls.private_page = make_studio_page(
			cls.app.name,
			page_title="Private Page",
			route="/private",
			blocks=frappe.as_json([component_ref(cls.secret_widget)]),
		)
		make_studio_page(cls.app.name, page_title="Draft Page", route="/draft", published=0, allow_guest=1)
		cls.members_app = make_studio_app(app_title="Members App", app_name="members-app")
		make_studio_page(cls.members_app.name, page_title="Members Home", route="/home")

	@classmethod
	def delete_leftover_fixtures(cls):
		"""Remove fixtures left behind when get_context commits."""
		for app_name in ("guest-test-app", "members-app"):
			if frappe.db.exists("Studio App", app_name):
				frappe.delete_doc("Studio App", app_name, force=True)
		component_names = ["Hero Section", "Nested Card", "Secret Widget"]
		for name in frappe.get_all(
			"Studio Component", filters={"component_name": ["in", component_names]}, pluck="name"
		):
			frappe.delete_doc("Studio Component", name, force=True)

	def as_guest(self):
		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")

	def test_guest_gets_public_page(self):
		self.as_guest()
		page = get_page(self.app.name, "/public")
		self.assertEqual(page["name"], self.public_page.name)

	def test_guest_gets_404_for_anything_not_public(self):
		self.as_guest()
		for route in ("/private", "/draft", "/nonexistent"):
			with self.assertRaises(frappe.DoesNotExistError):
				get_page(self.app.name, route)

	def test_guest_cannot_preview_public_pages(self):
		self.as_guest()
		with self.assertRaisesRegex(
			frappe.PermissionError, "You do not have permission to preview this page"
		):
			get_page(self.app.name, "/public", preview=True)

	def test_logged_in_user_gets_private_page(self):
		page = get_page(self.app.name, "/private")
		self.assertEqual(page["name"], self.private_page.name)

	def test_renderer_serves_guests_only_apps_with_public_pages(self):
		self.as_guest()
		renderer = StudioAppRenderer(path=f"{self.app.route}/public")
		self.assertTrue(renderer.can_render())
		self.assertTrue(renderer.can_render_for_guest())

		members_renderer = StudioAppRenderer(path=f"{self.members_app.route}/home")
		self.assertTrue(members_renderer.can_render())
		self.assertFalse(members_renderer.can_render_for_guest())
		with self.assertRaises(frappe.Redirect):
			members_renderer.render()

	def test_renderer_never_serves_previews_to_guests(self):
		self.as_guest()
		renderer = StudioAppRenderer(path=f"dev/{self.app.route}/public")
		self.assertTrue(renderer.can_render())
		self.assertFalse(renderer.can_render_for_guest())
		with self.assertRaises(frappe.Redirect):
			renderer.render()

	def test_app_pages_filtered_for_guest(self):
		self.as_guest()
		context = frappe._dict()
		self.app.get_context(context)
		self.assertTrue(context.is_guest)
		self.assertEqual([page.route for page in context.app_pages], ["/public"])

	def test_app_pages_unfiltered_for_logged_in_user(self):
		context = frappe._dict()
		self.app.get_context(context)
		self.assertFalse(context.is_guest)
		self.assertEqual({page.route for page in context.app_pages}, {"/public", "/private"})

	def test_page_ships_its_component_definitions(self):
		self.as_guest()
		page = get_page(self.app.name, "/public")
		components = {component["name"]: component for component in page["components"]}
		self.assertEqual(set(components), {self.hero.name, self.nested_card.name})
		self.assertEqual(components[self.hero.name]["inputs"][0]["input_name"], "title")
		self.assertEqual(components[self.nested_card.name]["inputs"], [])

	def test_get_page_is_guest_whitelisted(self):
		self.as_guest()
		frappe.is_whitelisted(get_page)
