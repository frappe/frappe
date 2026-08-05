# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.tests import IntegrationTestCase


class TestWorkspace(IntegrationTestCase):
	def setUp(self):
		create_module("Test Module")

	def tearDown(self):
		frappe.db.delete("Workspace", {"module": "Test Module"})
		frappe.db.delete("DocType", {"module": "Test Module"})
		frappe.delete_doc("Module Def", "Test Module")

	def test_workspace_conflicts_with_existing_doctype(self):
		"""Workspace name should not conflict with existing DocType names."""

		create_doctype("Test", "Test Module")
		workspace = create_workspace(name="Test", label="Test", public=1, title="Test")

		with self.assertRaises(frappe.NameError):
			workspace.insert()

	# TODO: FIX ME - flaky test!!!
	# def test_workspace_with_cards_specific_to_a_country(self):
	# 	workspace = create_workspace()
	# 	insert_card(workspace, "Card Label 1", "DocType 1", "DocType 2", "France")
	# 	insert_card(workspace, "Card Label 2", "DocType A", "DocType B")

	# 	workspace.insert(ignore_if_duplicate = True)

	# 	cards = workspace.get_link_groups()

	# 	if frappe.get_system_settings('country') == "France":
	# 		self.assertEqual(len(cards), 2)
	# 	else:
	# 		self.assertEqual(len(cards), 1)
	def test_save_page_with_new_widgets_as_dict(self):
		"""save_page receives new_widgets already parsed into a dict by the request layer."""
		from frappe.desk.doctype.workspace.workspace import save_page

		workspace = frappe.new_doc("Workspace")
		workspace.label = "New Widget Test Workspace"
		workspace.title = "New Widget Test Workspace"
		workspace.public = 0
		workspace.for_user = frappe.session.user
		workspace.content = "[]"
		workspace.insert()

		blocks = json.dumps(
			[{"id": "abcdef1234", "type": "shortcut", "data": {"shortcut_name": "ToDo", "col": 4}}]
		)

		try:
			save_page(
				name=workspace.name,
				public=0,
				new_widgets={"shortcut": [{"type": "DocType", "link_to": "ToDo", "label": "ToDo"}]},
				blocks=blocks,
			)

			saved = frappe.get_doc("Workspace", workspace.name)
			self.assertEqual([shortcut.label for shortcut in saved.shortcuts], ["ToDo"])
		finally:
			frappe.db.delete("Workspace", {"name": workspace.name})

<<<<<<< HEAD
=======
	def test_duplicate_shortcut_labels_are_rejected(self):
		"""Two shortcuts sharing a label would collapse into one row on save, so block it."""
		workspace = frappe.new_doc("Workspace")
		workspace.label = "Duplicate Shortcut Workspace"
		workspace.title = "Duplicate Shortcut Workspace"
		workspace.public = 0
		workspace.for_user = frappe.session.user
		workspace.content = "[]"

		for stats_filter in (
			'[["ToDo","status","!=","Open",false]]',
			'[["ToDo","status","=","Closed",false]]',
		):
			workspace.append(
				"shortcuts",
				{"type": "DocType", "link_to": "ToDo", "label": "Tasks", "stats_filter": stats_filter},
			)

		try:
			with self.assertRaises(frappe.ValidationError):
				workspace.insert()
		finally:
			frappe.db.delete("Workspace", {"name": workspace.name})

	def test_preexisting_duplicate_labels_stay_editable(self):
		"""Duplicates already stored (shipped app data, older sites) must not lock the workspace."""
		workspace = frappe.new_doc("Workspace")
		workspace.label = "Legacy Duplicate Workspace"
		workspace.title = "Legacy Duplicate Workspace"
		workspace.public = 0
		workspace.for_user = frappe.session.user
		workspace.content = "[]"
		workspace.insert()

		try:
			# simulate data that predates the check, bypassing validate()
			for idx in (1, 2):
				frappe.get_doc(
					{
						"doctype": "Workspace Shortcut",
						"parent": workspace.name,
						"parenttype": "Workspace",
						"parentfield": "shortcuts",
						"idx": idx,
						"type": "DocType",
						"link_to": "ToDo",
						"label": "Tasks",
					}
				).db_insert()

			workspace.reload()
			self.assertEqual(len(workspace.shortcuts), 2)

			# an unrelated edit still saves; the grandfathered duplicate is not re-raised
			workspace.title = "Legacy Duplicate Workspace Renamed"
			workspace.save()

			# deepening the existing clash -- a *third* row under the grandfathered label -- is a
			# new duplicate all the same, so it is still refused
			workspace.append("shortcuts", {"type": "DocType", "link_to": "ToDo", "label": "Tasks"})
			with self.assertRaises(frappe.ValidationError):
				workspace.save()

			# and so is a fresh clash on a label that was unique before
			workspace.reload()
			for _ in range(2):
				workspace.append("shortcuts", {"type": "DocType", "link_to": "ToDo", "label": "Notes"})
			with self.assertRaises(frappe.ValidationError):
				workspace.save()

			# dropping one of the grandfathered rows is a repair, not a new clash
			workspace.reload()
			workspace.shortcuts.pop()
			workspace.save()
			self.assertEqual(len(workspace.shortcuts), 1)
		finally:
			frappe.db.delete("Workspace Shortcut", {"parent": workspace.name})
			frappe.db.delete("Workspace", {"name": workspace.name})

	def test_role_restricted_non_public_workspace_visible_to_permitted_user(self):
		"""Non-public workspace with roles should be visible to users with matching role."""
		from frappe.desk.desktop import get_workspaces

		workspace = frappe.new_doc("Workspace")
		workspace.label = "Role Test Workspace"
		workspace.title = "Role Test Workspace"
		workspace.category = "Modules"
		workspace.public = 0
		workspace.module = "Desk"
		workspace.append("roles", {"role": "System Manager"})
		workspace.insert(ignore_if_duplicate=True)

		try:
			result = get_workspaces()
			workspace_titles = [p.title for p in result["pages"]]
			self.assertIn("Role Test Workspace", workspace_titles)
		finally:
			frappe.db.delete("Workspace", {"name": workspace.name})

>>>>>>> 904feca12c (fix(ux): show warning over same label)

def create_module(module_name):
	module = frappe.get_doc({"doctype": "Module Def", "module_name": module_name, "app_name": "frappe"})
	module.insert(ignore_if_duplicate=True)

	return module


def create_workspace(**args):
	workspace = frappe.new_doc("Workspace")
	args = frappe._dict(args)

	workspace.name = args.name or "Test Workspace"
	workspace.label = args.label or "Test Workspace"
	workspace.category = args.category or "Modules"
	workspace.is_standard = args.is_standard or 1
	workspace.module = "Test Module"
	workspace.public = args.public or 0
	workspace.title = args.title or "Test Workspace"

	return workspace


def insert_card(workspace, card_label, doctype1, doctype2, country=None):
	workspace.append("links", {"type": "Card Break", "label": card_label, "only_for": country})

	create_doctype(doctype1, "Test Module")
	workspace.append(
		"links",
		{
			"type": "Link",
			"label": doctype1,
			"only_for": country,
			"link_type": "DocType",
			"link_to": doctype1,
		},
	)

	create_doctype(doctype2, "Test Module")
	workspace.append(
		"links",
		{
			"type": "Link",
			"label": doctype2,
			"only_for": country,
			"link_type": "DocType",
			"link_to": doctype2,
		},
	)


def create_doctype(doctype_name, module):
	frappe.get_doc(
		{
			"doctype": "DocType",
			"name": doctype_name,
			"module": module,
			"custom": 1,
			"autoname": "field:title",
			"fields": [
				{"label": "Title", "fieldname": "title", "reqd": 1, "fieldtype": "Data"},
				{"label": "Description", "fieldname": "description", "fieldtype": "Small Text"},
				{"label": "Date", "fieldname": "date", "fieldtype": "Date"},
				{"label": "Duration", "fieldname": "duration", "fieldtype": "Duration"},
				{"label": "Number", "fieldname": "number", "fieldtype": "Int"},
				{"label": "Number", "fieldname": "another_number", "fieldtype": "Int"},
			],
			"permissions": [{"role": "System Manager"}],
		}
	).insert(ignore_if_duplicate=True)
