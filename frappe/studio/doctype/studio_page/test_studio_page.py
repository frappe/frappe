# Copyright (c) 2024, Frappe Technologies Pvt Ltd and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from studio.studio.doctype.studio_app.studio_app import StudioAppRenderer
from studio.studio.doctype.studio_app.test_studio_app import make_studio_app, make_studio_page
from studio.studio.doctype.studio_page.studio_page import get_page


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
