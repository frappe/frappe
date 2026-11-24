# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestAPrivatePageIsItsOwners(FrappeTestCase):
	"""A private page is read and written by the user named in `for_user` and by a Workspace Manager."""

	MODULE = "Desk"
	PAGE = "Test Private Page Of Its Owner"
	PUBLIC_PAGE = "Test Public Page Nobody Owns"
	OWNER = "test-private-page-owner@example.com"
	OTHER = "test-private-page-other@example.com"
	MANAGER = "test-private-page-manager@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		for email, roles in (
			(self.OWNER, ["Desk User"]),
			(self.OTHER, ["Desk User"]),
			(self.MANAGER, ["Desk User", "Workspace Manager"]),
		):
			frappe.delete_doc("User", email, force=True, ignore_missing=True)
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Page",
					"send_welcome_email": 0,
					"roles": [{"role": role} for role in roles],
				}
			).insert()
			self.addCleanup(frappe.delete_doc, "User", email, force=True, ignore_missing=True)

		frappe.set_user(self.OWNER)
		self.make_page(self.PAGE, public=0, for_user=self.OWNER)
		frappe.set_user("Administrator")
		self.make_page(self.PUBLIC_PAGE, public=1)

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in (self.PAGE, self.PUBLIC_PAGE):
			frappe.delete_doc("Workspace", name, force=True, ignore_missing=True)

	def make_page(self, title, **fields):
		return frappe.get_doc(
			{
				"doctype": "Workspace",
				"label": title,
				"title": title,
				"module": self.MODULE,
				"content": "[]",
				**fields,
			}
		).insert()

	def test_nobody_else_sees_it(self):
		from frappe.desk.desktop import get_desktop_page

		frappe.set_user(self.OTHER)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Workspace", self.PAGE).check_permission("read")
		with self.assertRaises(frappe.PermissionError):
			get_desktop_page(json.dumps({"name": self.PAGE, "title": self.PAGE}))
		self.assertNotIn(
			self.PAGE, frappe.get_list("Workspace", pluck="name", filters={"module": self.MODULE})
		)

		frappe.set_user(self.OWNER)
		self.assertIn(self.PAGE, frappe.get_list("Workspace", pluck="name", filters={"module": self.MODULE}))

	def test_nobody_else_takes_or_deletes_it(self):
		from frappe.client import delete, set_value

		frappe.set_user(self.OTHER)
		with self.assertRaises(frappe.PermissionError):
			set_value("Workspace", self.PAGE, "for_user", self.OTHER)
		with self.assertRaises(frappe.PermissionError):
			delete("Workspace", self.PAGE)
		# `disable_saving_as_public` is true in every test, and it is what lifts this rule for an
		# install or a migration.
		with (
			patch("frappe.desk.doctype.workspace.workspace.disable_saving_as_public", return_value=False),
			self.assertRaises(frappe.ValidationError),
		):
			set_value("Workspace", self.PUBLIC_PAGE, {"public": 0, "for_user": self.OTHER})

		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Workspace", self.PAGE, "for_user"), self.OWNER)
		self.assertEqual(frappe.db.get_value("Workspace", self.PUBLIC_PAGE, "public"), 1)

	def test_a_workspace_manager_still_moves_it(self):
		from frappe.client import set_value

		frappe.set_user(self.MANAGER)
		set_value("Workspace", self.PAGE, "for_user", self.MANAGER)

		self.assertEqual(frappe.db.get_value("Workspace", self.PAGE, "for_user"), self.MANAGER)


class TestWorkspace(FrappeTestCase):
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

	def test_update_page_on_public_workspace_needs_workspace_manager(self):
		from frappe.desk.doctype.workspace.workspace import update_page

		workspace = frappe.get_doc(
			{
				"doctype": "Workspace",
				"label": "Test Public",
				"title": "Test Public",
				"public": 1,
				"content": "[]",
			}
		).insert()
		self.addCleanup(frappe.delete_doc, "Workspace", workspace.name, force=True)

		with self.set_user("test1@example.com"), self.assertRaises(frappe.PermissionError):
			update_page(workspace.name, "Stolen", "", "", "", 0)

		self.assertEqual(frappe.db.get_value("Workspace", workspace.name, "public"), 1)

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
