# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from json import dumps, loads
from unittest.mock import patch

import frappe
from frappe.desk.doctype.workspace_customization.workspace_customization import (
	apply_customization,
	effective_roles,
	reset_workspace_customization,
)
from frappe.tests import IntegrationTestCase

BASE_CONTENT = [
	{"id": "s1", "type": "shortcut", "data": {"shortcut_name": "My ToDos", "col": 4}},
	{"id": "s2", "type": "shortcut", "data": {"shortcut_name": "My Notes", "col": 4}},
]

ADDED_SHORTCUT_BLOCK = {"id": "x", "type": "shortcut", "data": {"shortcut_name": "Audit", "col": 4}}
ADDED_SHORTCUT_ITEM = {"type": "DocType", "link_to": "Activity Log", "label": "Audit"}


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
		elif key in ("content", "widgets"):
			doc.set(key, dumps(value))
		else:
			doc.set(key, value)
	return doc


class TestWorkspaceCustomizationUnit(IntegrationTestCase):
	"""Pure merge logic on in-memory docs (no DB / link validation)."""

	def test_content_snapshot_is_shown_verbatim(self):
		doc = make_base_doc()
		snapshot = [BASE_CONTENT[0]]  # the site dropped "My Notes" and kept only "My ToDos"
		apply_customization(doc, make_customization(content=snapshot))
		self.assertEqual(loads(doc.content), snapshot)

	def test_added_widget_item_is_appended(self):
		doc = make_base_doc()
		snapshot = [*BASE_CONTENT, ADDED_SHORTCUT_BLOCK]
		apply_customization(
			doc,
			make_customization(content=snapshot, widgets={"shortcut": [ADDED_SHORTCUT_ITEM]}),
		)
		self.assertIn("Audit", [s.label for s in doc.shortcuts])

	def test_content_untouched_when_only_visibility_customized(self):
		doc = make_base_doc()
		apply_customization(doc, make_customization(visibility="Hidden"))
		self.assertEqual(loads(doc.content), BASE_CONTENT)
		self.assertTrue(doc.is_hidden)

	def test_effective_roles_add_and_remove(self):
		customization = make_customization(added_roles=["Boss"], removed_roles=["Stock User"])
		roles = set(effective_roles(["Stock User", "Stock Manager"], customization))
		self.assertEqual(roles, {"Stock Manager", "Boss"})

	def test_roles_flow_through_when_app_adds_a_role(self):
		# the delta only remembers "+Boss / -Stock User"; a role the app later adds to the
		# base must still appear (proves roles layer on the live base, not a frozen copy).
		customization = make_customization(added_roles=["Boss"], removed_roles=["Stock User"])
		roles = set(effective_roles(["Stock User", "Stock Manager", "Stock Auditor"], customization))
		self.assertEqual(roles, {"Stock Manager", "Stock Auditor", "Boss"})


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

	def test_save_page_stores_snapshot_and_leaves_base_untouched(self):
		from frappe.desk.doctype.workspace.workspace import save_page

		edited = [BASE_CONTENT[0]]  # drop "My Notes"
		# force the site (non-developer) path: a standard workspace edit goes to the delta
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			save_page(self.WORKSPACE, public=1, new_widgets={}, blocks=dumps(edited))

		customization = frappe.get_doc("Workspace Customization", self.WORKSPACE)
		self.assertEqual(loads(customization.content), edited)
		# the app-owned record still has BOTH blocks -- it was never edited in place
		base_content = loads(frappe.db.get_value("Workspace", self.WORKSPACE, "content"))
		self.assertEqual(len(base_content), 2)

	def test_get_workspaces_renders_snapshot_content(self):
		frappe.get_doc(
			{
				"doctype": "Workspace Customization",
				"workspace": self.WORKSPACE,
				"content": dumps([BASE_CONTENT[0]]),
			}
		).insert()

		from frappe.desk.desktop import get_workspaces

		page = next(p for p in get_workspaces()["pages"] if p["name"] == self.WORKSPACE)
		self.assertEqual(loads(page["content"]), [BASE_CONTENT[0]])

	def test_get_desktop_page_includes_added_widget(self):
		frappe.get_doc(
			{
				"doctype": "Workspace Customization",
				"workspace": self.WORKSPACE,
				"content": dumps([*BASE_CONTENT, ADDED_SHORTCUT_BLOCK]),
				"widgets": dumps({"shortcut": [ADDED_SHORTCUT_ITEM]}),
			}
		).insert()

		from frappe.desk.desktop import get_desktop_page

		result = get_desktop_page({"name": self.WORKSPACE, "title": self.WORKSPACE, "public": 1})
		self.assertIn("Audit", [s.label for s in result["shortcuts"]["items"]])

	def test_added_widget_persists_across_a_second_save(self):
		from frappe.desk.doctype.workspace.workspace import save_page

		with patch.dict(frappe.conf, {"developer_mode": 0}):
			# session 1: add "Audit"
			save_page(
				self.WORKSPACE,
				public=1,
				new_widgets={"shortcut": [ADDED_SHORTCUT_ITEM]},
				blocks=dumps([*BASE_CONTENT, ADDED_SHORTCUT_BLOCK]),
			)
			# session 2: an unrelated edit reports no new widgets, but "Audit" must survive
			save_page(
				self.WORKSPACE,
				public=1,
				new_widgets={},
				blocks=dumps([BASE_CONTENT[0], ADDED_SHORTCUT_BLOCK]),
			)
		widgets = loads(frappe.db.get_value("Workspace Customization", self.WORKSPACE, "widgets"))
		self.assertEqual([w["label"] for w in widgets["shortcut"]], ["Audit"])

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
