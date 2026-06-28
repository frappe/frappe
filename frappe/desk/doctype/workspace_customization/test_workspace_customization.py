# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from json import dumps, loads

import frappe
from frappe.desk.doctype.workspace_customization.workspace_customization import (
	apply_customization,
	block_key,
	diff_customization,
	effective_roles,
	reset_workspace_customization,
)
from frappe.tests import IntegrationTestCase

BASE_CONTENT = [
	{"id": "s1", "type": "shortcut", "data": {"shortcut_name": "My ToDos", "col": 4}},
	{"id": "s2", "type": "shortcut", "data": {"shortcut_name": "My Notes", "col": 4}},
]


def make_base_doc():
	"""An in-memory standard Workspace doc with two shortcut blocks (not inserted)."""
	doc = frappe.new_doc("Workspace")
	doc.label = doc.title = "Customization Test"
	doc.module = "Desk"
	doc.public = 1
	doc.standard = 1
	doc.content = dumps(BASE_CONTENT)
	doc.append("shortcuts", {"type": "DocType", "link_to": "ToDo", "label": "My ToDos"})
	doc.append("shortcuts", {"type": "DocType", "link_to": "Note", "label": "My Notes"})
	doc.append("roles", {"role": "Stock User"})
	doc.append("roles", {"role": "Stock Manager"})
	return doc


def make_customization(**values):
	doc = frappe.new_doc("Workspace Customization")
	doc.workspace = "Customization Test"
	for key, value in values.items():
		if key in ("added_roles", "removed_roles"):
			for role in value:
				doc.append(key, {"role": role})
		elif key == "content_delta":
			doc.content_delta = dumps(value)
		else:
			doc.set(key, value)
	return doc


class TestWorkspaceCustomizationUnit(IntegrationTestCase):
	"""Pure merge/diff logic on in-memory docs (no DB / link validation)."""

	def test_block_key_uses_semantic_identity_not_editor_id(self):
		block = {"id": "throwaway", "type": "shortcut", "data": {"shortcut_name": "My ToDos"}}
		self.assertEqual(block_key(block), "shortcut:My ToDos")

	def test_hidden_block_drops_block_and_child_row(self):
		doc = make_base_doc()
		apply_customization(doc, make_customization(content_delta={"hidden_blocks": ["shortcut:My Notes"]}))

		keys = [block_key(b) for b in loads(doc.content)]
		self.assertEqual(keys, ["shortcut:My ToDos"])
		self.assertEqual([s.label for s in doc.shortcuts], ["My ToDos"])

	def test_added_block_appends_block_and_item(self):
		doc = make_base_doc()
		delta = {
			"added_blocks": [
				{
					"block": {"id": "x", "type": "shortcut", "data": {"shortcut_name": "Audit"}},
					"item": {"type": "DocType", "link_to": "Activity Log", "label": "Audit"},
				}
			]
		}
		apply_customization(doc, make_customization(content_delta=delta))

		self.assertIn("shortcut:Audit", [block_key(b) for b in loads(doc.content)])
		self.assertIn("Audit", [s.label for s in doc.shortcuts])

	def test_block_override_changes_presentation(self):
		doc = make_base_doc()
		delta = {"block_overrides": {"shortcut:My ToDos": {"label": "Tasks", "col": 6}}}
		apply_customization(doc, make_customization(content_delta=delta))

		todo_block = next(b for b in loads(doc.content) if block_key(b) == "shortcut:My ToDos")
		self.assertEqual(todo_block["data"]["col"], 6)
		self.assertEqual(next(s for s in doc.shortcuts if s.link_to == "ToDo").label, "Tasks")

	def test_block_order_reorders(self):
		doc = make_base_doc()
		delta = {"block_order": ["shortcut:My Notes", "shortcut:My ToDos"]}
		apply_customization(doc, make_customization(content_delta=delta))
		self.assertEqual(
			[block_key(b) for b in loads(doc.content)],
			["shortcut:My Notes", "shortcut:My ToDos"],
		)

	def test_effective_roles_add_and_remove(self):
		customization = make_customization(added_roles=["Boss"], removed_roles=["Stock User"])
		roles = set(effective_roles(["Stock User", "Stock Manager"], customization))
		self.assertEqual(roles, {"Stock Manager", "Boss"})

	def test_roles_flow_through_when_app_adds_a_role(self):
		# the delta only remembers "+Boss / -Stock User"; a role the app later adds to the
		# base must still appear (proves we layer on the live base, not a frozen copy).
		customization = make_customization(added_roles=["Boss"], removed_roles=["Stock User"])
		roles = set(effective_roles(["Stock User", "Stock Manager", "Stock Auditor"], customization))
		self.assertEqual(roles, {"Stock Manager", "Stock Auditor", "Boss"})

	def test_diff_then_apply_roundtrips(self):
		base = make_base_doc()
		# edited = hide "My Notes" + add "Audit"
		edited_content = [
			BASE_CONTENT[0],
			{"id": "x", "type": "shortcut", "data": {"shortcut_name": "Audit"}},
		]
		new_widgets = {"shortcut": [{"type": "DocType", "link_to": "Activity Log", "label": "Audit"}]}

		delta = diff_customization(base, edited_content, new_widgets)
		self.assertEqual(delta["hidden_blocks"], ["shortcut:My Notes"])
		self.assertEqual([a["block"]["data"]["shortcut_name"] for a in delta["added_blocks"]], ["Audit"])

		merged = make_base_doc()
		apply_customization(merged, make_customization(content_delta=delta))
		self.assertEqual(
			[block_key(b) for b in loads(merged.content)],
			["shortcut:My ToDos", "shortcut:Audit"],
		)


class TestWorkspaceCustomizationIntegration(IntegrationTestCase):
	WORKSPACE = "WC Integration Test"

	def setUp(self):
		frappe.set_user("Administrator")
		ws = frappe.new_doc("Workspace")
		ws.label = ws.title = self.WORKSPACE
		ws.module = "Desk"
		ws.public = 1
		ws.standard = 1
		ws.content = dumps(BASE_CONTENT)
		ws.append("shortcuts", {"type": "DocType", "link_to": "ToDo", "label": "My ToDos"})
		ws.append("shortcuts", {"type": "DocType", "link_to": "Note", "label": "My Notes"})
		ws.insert(ignore_if_duplicate=True)

	def tearDown(self):
		frappe.delete_doc_if_exists("Workspace Customization", self.WORKSPACE)
		frappe.db.delete("Workspace", {"name": self.WORKSPACE})

	def test_save_page_on_standard_creates_delta_and_leaves_base_untouched(self):
		from frappe.desk.doctype.workspace.workspace import save_page

		edited = [BASE_CONTENT[0]]  # drop "My Notes"
		save_page(self.WORKSPACE, public=1, new_widgets="{}", blocks=dumps(edited))

		self.assertTrue(frappe.db.exists("Workspace Customization", self.WORKSPACE))
		# the app-owned record still has BOTH blocks -- it was never edited in place
		base_content = loads(frappe.db.get_value("Workspace", self.WORKSPACE, "content"))
		self.assertEqual(len(base_content), 2)

	def test_get_desktop_page_returns_merged_content(self):
		frappe.get_doc(
			{
				"doctype": "Workspace Customization",
				"workspace": self.WORKSPACE,
				"content_delta": dumps({"hidden_blocks": ["shortcut:My Notes"]}),
			}
		).insert()

		from frappe.desk.desktop import get_desktop_page

		result = get_desktop_page({"name": self.WORKSPACE, "title": self.WORKSPACE, "public": 1})
		labels = [s.label for s in result["shortcuts"]["items"]]
		self.assertIn("My ToDos", labels)
		self.assertNotIn("My Notes", labels)

	def test_reset_removes_customization(self):
		frappe.get_doc(
			{"doctype": "Workspace Customization", "workspace": self.WORKSPACE, "visibility": "Hidden"}
		).insert()
		self.assertTrue(frappe.db.exists("Workspace Customization", self.WORKSPACE))

		reset_workspace_customization(self.WORKSPACE)
		self.assertFalse(frappe.db.exists("Workspace Customization", self.WORKSPACE))

	def test_customization_requires_standard_workspace(self):
		private = frappe.new_doc("Workspace")
		private.label = private.title = "WC Private Test"
		private.module = "Desk"
		private.public = 0
		private.standard = 0
		private.content = "[]"
		private.insert(ignore_if_duplicate=True)
		try:
			with self.assertRaises(frappe.ValidationError):
				frappe.get_doc({"doctype": "Workspace Customization", "workspace": private.name}).insert()
		finally:
			frappe.db.delete("Workspace", {"name": private.name})
