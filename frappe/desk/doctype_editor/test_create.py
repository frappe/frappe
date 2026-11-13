# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
from frappe.desk.doctype_editor.create import create_doctype
from frappe.desk.doctype_editor.test_save_design import delete_committed, details_rows
from frappe.tests import IntegrationTestCase

DOCTYPE = "Test Editor Create 47272"
SYSTEM_MANAGER = "system-manager-47272@example.com"
DETAILS = {"type": "Details"}


def definition(**kwargs) -> dict:
	return {
		"name": DOCTYPE,
		"module": "Custom",
		"custom": 1,
		"fields": [
			{"fieldname": "title", "label": "Title", "fieldtype": "Data"},
			{"fieldname": "notes", "label": "Notes", "fieldtype": "Text"},
		],
		**kwargs,
	}


def two_tabs() -> list:
	return [
		{
			"name": "details_tab",
			"label": "Details",
			"sections": [{"name": "main_section", "columns": [{"name": "column_1", "fields": ["title"]}]}],
		},
		{
			"name": "more_tab",
			"label": "More",
			"sections": [
				{
					"name": "notes_section",
					"columns": [
						{"name": "column_1", "fields": ["notes"]},
						{"name": "column_2", "fields": []},
					],
				}
			],
		},
	]


def make_user(email: str, roles: list[str]):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Editor",
				"roles": [{"role": role} for role in roles],
			}
		).insert()


def drop_doctype():
	frappe.db.delete("Form Layout", {"dt": DOCTYPE})
	delete_committed("DocType", DOCTYPE)


class TestCreateDoctype(IntegrationTestCase):
	def setUp(self):
		drop_doctype()
		self.addCleanup(drop_doctype)
		make_user(SYSTEM_MANAGER, ["System Manager"])
		self.addCleanup(delete_committed, "User", SYSTEM_MANAGER)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(SYSTEM_MANAGER)

	def test_a_custom_doctype_is_created_with_its_details_layout(self):
		result = create_doctype(definition(), two_tabs(), [])
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertEqual(result["doctype"], DOCTYPE)
		self.assertEqual(
			result["base_version"]["doctype"], str(frappe.db.get_value("DocType", DOCTYPE, "modified"))
		)
		self.assertEqual(frappe.get_meta(DOCTYPE).get_field("notes").fieldtype, "Text")
		[row] = details_rows(DOCTYPE)
		tabs = json.loads(row.layout)
		self.assertEqual([tab["name"] for tab in tabs], ["details_tab", "more_tab"])
		self.assertEqual(tabs[1]["sections"][0]["columns"][0]["fields"], ["notes"])

	def test_edits_apply_on_top_of_the_layout(self):
		edits = [
			{
				"act": "fields.add_field",
				"label": "Due Date",
				"fieldtype": "Date",
				"layout": DETAILS,
				"section": "notes_section",
				"column": "column_2",
				"index": 0,
			}
		]
		result = create_doctype(definition(), two_tabs(), edits)
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertEqual(frappe.get_meta(DOCTYPE).get_field("due_date").fieldtype, "Date")
		[row] = details_rows(DOCTYPE)
		self.assertEqual(json.loads(row.layout)[1]["sections"][0]["columns"][1]["fields"], ["due_date"])

	def test_a_failed_edit_leaves_no_doctype_behind(self):
		edits = [
			{"act": "canvas.place_field", "layout": DETAILS, "fieldname": "missing", "column": "column_1"}
		]
		result = create_doctype(definition(), two_tabs(), edits)
		self.assertFalse(result["saved"])
		[error] = result["errors"]
		self.assertEqual(error["target"], {"kind": "field", "fieldname": "missing"})
		self.assertEqual(error["edit"], 0)
		self.assertFalse(frappe.db.exists("DocType", DOCTYPE))
		self.assertFalse(frappe.db.table_exists(DOCTYPE))
		self.assertFalse(details_rows(DOCTYPE))

	def test_a_definition_failing_validation_leaves_no_doctype_behind(self):
		fields = [{"fieldname": "status", "label": "Status", "fieldtype": "Link"}]
		result = create_doctype(definition(fields=fields), None, [])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"], {"kind": "banner"})
		self.assertFalse(frappe.db.exists("DocType", DOCTYPE))

	def test_a_system_manager_full_rights_permission_is_added(self):
		result = create_doctype(definition(), two_tabs(), [])
		self.assertTrue(result["saved"], result.get("errors"))
		[perm] = frappe.get_doc("DocType", DOCTYPE).permissions
		self.assertEqual(perm.role, "System Manager")
		self.assertTrue(perm.read and perm.write and perm.create and perm.delete)

	def test_an_existing_name_is_refused(self):
		modified = frappe.db.get_value("DocType", "ToDo", "modified")
		result = create_doctype(definition(name="ToDo"), two_tabs(), [])
		self.assertFalse(result["saved"])
		self.assertIn("ToDo", result["errors"][0]["message"])
		self.assertEqual(frappe.db.get_value("DocType", "ToDo", "modified"), modified)

	def test_a_standard_doctype_needs_developer_mode(self):
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			with self.assertRaises(frappe.PermissionError):
				create_doctype(definition(custom=0, module="Desk"), two_tabs(), [])
		self.assertFalse(frappe.db.exists("DocType", DOCTYPE))

	def test_a_user_without_system_manager_is_refused(self):
		user = "no-system-manager-47272@example.com"
		make_user(user, [])
		self.addCleanup(delete_committed, "User", user)
		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			create_doctype(definition(), two_tabs(), [])
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("DocType", DOCTYPE))
