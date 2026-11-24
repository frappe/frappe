from unittest.mock import patch

import frappe
from frappe.desk.workspace_component import get_workspace_component, make_workspace_component
from frappe.studio.desk import get_desk_component, get_desk_components
from frappe.tests import IntegrationTestCase

DESK_USER = "workspace-component-reader@example.com"

CONTENT = [
	{
		"id": "h1",
		"type": "header",
		"data": {"text": '<span class="h4"><b>Your Shortcuts</b></span>', "col": 12},
	},
	{"id": "s1", "type": "shortcut", "data": {"shortcut_name": "To-dos", "col": 3}},
	{"id": "s2", "type": "shortcut", "data": {"shortcut_name": "Roles", "col": 3}},
	{"id": "c1", "type": "card", "data": {"card_name": "Open", "col": 4}},
	{"id": "c2", "type": "card", "data": {"card_name": "Restricted", "col": 4}},
	{"id": "n1", "type": "number_card", "data": {"number_card_name": "Row that is gone", "col": 4}},
	{"id": "o1", "type": "onboarding", "data": {"onboarding_name": "Some Onboarding", "col": 12}},
]


def make_workspace(**values):
	doc = frappe.new_doc("Workspace")
	doc.update(
		{
			"label": "Component Test " + frappe.generate_hash(length=8),
			"title": "Component Test",
			"module": "Desk",
			"public": 1,
			"content": frappe.as_json(CONTENT),
			**values,
		}
	)
	doc.append("shortcuts", {"label": "To-dos", "type": "DocType", "link_to": "ToDo"})
	doc.append("shortcuts", {"label": "Roles", "type": "DocType", "link_to": "Role"})
	doc.append("links", {"type": "Card Break", "label": "Open"})
	doc.append("links", {"type": "Link", "label": "To-do", "link_type": "DocType", "link_to": "ToDo"})
	doc.append("links", {"type": "Link", "label": "Role", "link_type": "DocType", "link_to": "Role"})
	doc.append("links", {"type": "Card Break", "label": "Restricted"})
	doc.append("links", {"type": "Link", "label": "Role", "link_type": "DocType", "link_to": "Role"})
	return doc.insert()


def get_children(workspace: str) -> list[dict]:
	return frappe.parse_json(get_workspace_component(workspace)[0]["block"])["children"]


class TestWorkspaceComponent(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("User", DESK_USER):
			user = frappe.get_doc({"doctype": "User", "email": DESK_USER, "first_name": "Reader"})
			user.insert(ignore_permissions=True)
			user.add_roles("Desk User")

	def test_content_becomes_a_grid_of_widget_components(self):
		workspace = make_workspace()
		components = get_workspace_component(workspace.name)
		children = frappe.parse_json(components[0]["block"])["children"]

		# no component draws an onboarding yet, and the number card's row is gone
		self.assertEqual(
			[child["componentName"] for child in children],
			["TextBlock", "desk_shortcut", "desk_shortcut", "desk_links", "desk_links"],
		)
		self.assertEqual(children[0]["componentProps"]["text"], "Your Shortcuts")
		self.assertEqual(children[1]["baseStyles"]["gridColumn"], "span 3")
		self.assertEqual(children[1]["mobileStyles"]["gridColumn"], "span 12")
		self.assertEqual(children[1]["componentProps"]["link_to"], "ToDo")
		# the reply carries the widget components that the blocks use
		self.assertEqual(
			sorted(component["component_id"] for component in components[1:]), ["desk_links", "desk_shortcut"]
		)

	def test_a_user_gets_only_the_widgets_that_they_can_open(self):
		workspace = make_workspace()
		with self.set_user(DESK_USER):
			self.assertTrue(frappe.has_permission("ToDo"))
			self.assertFalse(frappe.has_permission("Role"))
			children = get_children(workspace.name)

		shortcuts = [
			c["componentProps"]["link_to"] for c in children if c["componentName"] == "desk_shortcut"
		]
		cards = [c["componentProps"] for c in children if c["componentName"] == "desk_links"]
		self.assertEqual(shortcuts, ["ToDo"])
		# a card with no link left is removed
		self.assertEqual([card["label"] for card in cards], ["Open"])
		self.assertEqual([link["link_to"] for link in cards[0]["links"]], ["ToDo"])

	def test_a_private_workspace_loads_for_its_user_only(self):
		workspace = make_workspace(public=0, for_user="Administrator")
		with self.set_user(DESK_USER):
			self.assertRaises(frappe.PermissionError, get_workspace_component, workspace.name)

	def test_a_workspace_gets_a_root_component_that_studio_can_edit(self):
		workspace = make_workspace()
		component_id = make_workspace_component(workspace.name)
		self.assertEqual(frappe.db.get_value("Workspace", workspace.name, "studio_component"), component_id)
		self.assertEqual(make_workspace_component(workspace.name), component_id)

		# the stored blocks are for every user, and each reply applies the reader's permissions
		component = frappe.get_doc("Studio Component", component_id)
		stored = frappe.parse_json(component.block)["children"]
		self.assertEqual(len([child for child in stored if child["componentName"] == "desk_shortcut"]), 2)
		stored.pop(0)
		component.block = {**frappe.parse_json(component.block), "children": stored}
		component.save()
		with self.set_user(DESK_USER):
			names = [child["componentName"] for child in get_children(workspace.name)]
		self.assertEqual(names, ["desk_shortcut", "desk_links"])

		# a root is not a widget: it loads through its workspace only
		self.assertRaises(frappe.DoesNotExistError, get_desk_component, component_id)
		self.assertNotIn(component_id, [row.component_id for row in get_desk_components()])

		frappe.get_doc("Workspace", workspace.name).delete()
		self.assertFalse(frappe.db.exists("Studio Component", component_id))

	def test_a_standard_workspace_gets_its_component_in_developer_mode_only(self):
		workspace = make_workspace()
		workspace.db_set("standard", 1)
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			self.assertRaises(frappe.ValidationError, make_workspace_component, workspace.name)
