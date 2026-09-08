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

		for _ in range(2):
			create_missing_dependencies(
				app.name, page_name=target.name, resources=deps["resources"], variables=deps["variables"]
			)

		target.reload()
		self.assertEqual([r.resource_name for r in target.resources], ["todos"])
		self.assertEqual([v.variable_name for v in target.variables], ["count"])

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
