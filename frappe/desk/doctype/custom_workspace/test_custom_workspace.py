# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from json import dumps, loads
from unittest.mock import patch

import frappe
from frappe.desk.doctype.custom_workspace.custom_workspace import (
	apply_customization,
	effective_renderer,
	effective_roles,
	reset_page_fields,
	upsert_property_customization,
)
from frappe.desk.layouts import with_ids
from frappe.tests import IntegrationTestCase

BASE_CONTENT = [
	{"id": "s1", "type": "shortcut", "data": {"shortcut_name": "My ToDos", "col": 4}},
	{"id": "s2", "type": "shortcut", "data": {"shortcut_name": "My Notes", "col": 4}},
]

ADDED_SHORTCUT_BLOCK = {"id": "x", "type": "shortcut", "data": {"shortcut_name": "Audit", "col": 4}}


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
	doc = frappe.new_doc("Custom Workspace")
	doc.workspace = "Customization Test"
	for key, value in values.items():
		if key in ("added_roles", "removed_roles"):
			for role in value:
				doc.append(key, {"role": role})
		else:
			doc.set(key, value)
	return doc


class TestCustomWorkspaceUnit(IntegrationTestCase):
	"""Pure merge logic on in-memory docs (no DB / link validation)."""

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

	def test_app_layout_change_reaches_a_workspace_customized_only_for_appearance(self):
		# the app ships a new block; a site that only set an icon / visibility has no snapshot
		# holding it back, so the new layout arrives.
		doc = make_base_doc()
		doc.content = dumps([*BASE_CONTENT, ADDED_SHORTCUT_BLOCK])
		apply_customization(doc, make_customization(icon="star", visibility="Hidden"))
		self.assertEqual(loads(doc.content), [*BASE_CONTENT, ADDED_SHORTCUT_BLOCK])
		self.assertEqual(doc.icon, "star")

	def test_effective_renderer(self):
		for app in ("Legacy", "Frappe UI"):
			for site, expected in (("Inherit", app), ("Frappe UI", "Frappe UI")):
				with self.subTest(app=app, site=site):
					customization = make_customization(renderer=site)
					self.assertEqual(effective_renderer(app, customization), expected)
					doc = make_base_doc()
					doc.renderer = app
					apply_customization(doc, customization)
					self.assertEqual(doc.renderer, expected)

	def test_the_site_row_takes_its_workspace_name(self):
		site = frappe.get_doc({"doctype": "Custom Workspace", "workspace": "Home"})
		site.autoname()
		self.assertEqual(site.name, "Home")


class TestCustomWorkspaceIntegration(IntegrationTestCase):
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
		frappe.delete_doc_if_exists("Custom Workspace", self.WORKSPACE)
		frappe.db.delete("Workspace", {"name": self.WORKSPACE})

	def test_reset_brings_back_the_apps_fields(self):
		frappe.get_doc(
			{
				"doctype": "Custom Workspace",
				"workspace": self.WORKSPACE,
				"visibility": "Hidden",
				"icon": "star",
			}
		).insert()

		reset_page_fields(self.WORKSPACE, ["visibility"])
		customization = frappe.get_doc("Custom Workspace", self.WORKSPACE)
		self.assertEqual((customization.visibility, customization.icon), ("Inherit", "star"))

		reset_page_fields(self.WORKSPACE)
		self.assertFalse(frappe.db.get_value("Custom Workspace", self.WORKSPACE, "icon"))

	def test_renderer_is_a_diff_and_reset_keeps_it(self):
		from frappe.desk.desktop import Workspace

		frappe.db.set_value("Workspace", self.WORKSPACE, "renderer", "Legacy")
		upsert_property_customization(self.WORKSPACE, renderer="Frappe UI")
		customization = frappe.get_doc("Custom Workspace", self.WORKSPACE)
		self.assertEqual(Workspace({"name": self.WORKSPACE}, minimal=True).doc.renderer, "Frappe UI")

		upsert_property_customization(self.WORKSPACE, visibility="Hidden")
		reset_page_fields(self.WORKSPACE)
		customization = frappe.get_doc("Custom Workspace", self.WORKSPACE)
		self.assertEqual(customization.visibility, "Inherit")
		self.assertEqual(Workspace({"name": self.WORKSPACE}, minimal=True).doc.renderer, "Frappe UI")

	def test_switching_renderer_freezes_nothing(self):
		from frappe.desk.doctype.workspace.workspace import set_workspace_renderer

		frappe.db.set_value("Workspace", self.WORKSPACE, "renderer", "Legacy")
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			set_workspace_renderer(self.WORKSPACE, "Frappe UI")
			customization = frappe.get_doc("Custom Workspace", self.WORKSPACE)
			self.assertEqual(customization.renderer, "Frappe UI")

			with self.assertRaises(frappe.ValidationError):
				set_workspace_renderer(self.WORKSPACE, "Legacy")
			with self.assertRaises(frappe.ValidationError):
				upsert_property_customization(self.WORKSPACE, renderer="Legacy")
			self.assertEqual(frappe.db.get_value("Custom Workspace", self.WORKSPACE, "renderer"), "Frappe UI")

			frappe.db.set_value("Workspace", self.WORKSPACE, "renderer", "Frappe UI")
			set_workspace_renderer(self.WORKSPACE, "Frappe UI")
		self.assertEqual(frappe.db.get_value("Custom Workspace", self.WORKSPACE, "renderer"), "Inherit")
		self.assertEqual(
			loads(frappe.db.get_value("Workspace", self.WORKSPACE, "content")), with_ids(BASE_CONTENT)
		)

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
				frappe.get_doc({"doctype": "Custom Workspace", "workspace": private.name}).insert()
		finally:
			frappe.db.delete("Workspace", {"name": private.name})
