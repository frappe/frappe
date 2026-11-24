import frappe
from frappe.studio.desk import get_desk_component, get_desk_components
from frappe.studio.doctype.studio_app.test_studio_app import make_studio_app
from frappe.studio.doctype.studio_page.test_studio_page import component_ref, make_component
from frappe.tests import IntegrationTestCase

DESK_USER = "desk-component-reader@example.com"
WEBSITE_USER = "desk-component-visitor@example.com"


def make_user(email: str, roles: list[str]) -> str:
	if not frappe.db.exists("User", email):
		user = frappe.get_doc({"doctype": "User", "email": email, "first_name": email.split("@")[0]})
		user.insert(ignore_permissions=True)
		user.add_roles(*roles)
	return email


class TestDesk(IntegrationTestCase):
	def setUp(self):
		make_user(DESK_USER, ["Desk User"])
		make_user(WEBSITE_USER, [])

	def test_a_desk_user_loads_a_global_component_with_the_components_inside_it(self):
		inner = make_component("Desk Inner")
		outer = make_component(
			"Desk Outer", block={"componentName": "div", "children": [component_ref(inner)]}
		)

		with self.set_user(DESK_USER):
			self.assertFalse(frappe.has_permission("Studio Component", "read", outer.name))
			components = get_desk_component(outer.component_id)

		self.assertEqual([c.component_id for c in components], [outer.component_id, inner.component_id])

	def test_only_a_desk_user_loads_a_component(self):
		component = make_component("Desk Guarded")
		with self.set_user(WEBSITE_USER):
			self.assertRaises(frappe.PermissionError, get_desk_component, component.component_id)
			self.assertRaises(frappe.PermissionError, get_desk_components)

	def test_desk_gets_only_enabled_global_components(self):
		app = make_studio_app(app_name="desk-" + frappe.generate_hash(length=8))
		of_app = frappe.get_doc(
			doctype="Studio Component", component_name="Desk Of App", studio_app=app.name
		).insert()
		disabled = make_component("Desk Disabled")
		disabled.db_set("is_disabled", 1)
		shown = make_component("Desk Shown")

		listed = [component.component_id for component in get_desk_components()]
		self.assertIn(shown.component_id, listed)
		self.assertNotIn(disabled.component_id, listed)
		self.assertNotIn(of_app.component_id, listed)
		for component in (of_app, disabled):
			self.assertRaises(frappe.DoesNotExistError, get_desk_component, component.component_id)
