# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.desk.doctype_editor.danger import (
	change_kind,
	delete_doctype,
	make_standard,
	move_doctype,
	rename_doctype,
	rename_effects,
)
from frappe.desk.doctype_editor.test_create import make_user
from frappe.desk.doctype_editor.test_save_design import delete_committed, make_custom_doctype
from frappe.modules.utils import doctype_python_modules
from frappe.tests import IntegrationTestCase

DOCTYPE = "Test Editor 47278"
RENAMED = "Test Editor 47278 Renamed"
PARENT = "Test Editor 47278 Parent"
SYSTEM_MANAGER = "danger-47278-sm@example.com"
NO_ROLES = "danger-47278-none@example.com"


class TestChangeKind(IntegrationTestCase):
	def setUp(self):
		make_custom_doctype(DOCTYPE)
		self.addCleanup(delete_committed, "DocType", DOCTYPE)

	def test_regular_to_child_is_refused_while_records_exist(self):
		frappe.get_doc({"doctype": DOCTYPE, "title": "One"}).insert()
		with self.assertRaises(frappe.ValidationError):
			change_kind(DOCTYPE, "child")
		self.assertEqual(frappe.db.get_value("DocType", DOCTYPE, "istable"), 0)

	def test_child_to_regular_is_refused_while_records_exist(self):
		change_kind(DOCTYPE, "child")
		row = {"doctype": DOCTYPE, "title": "One", "parent": "p", "parenttype": "Note", "parentfield": "rows"}
		frappe.get_doc(row).db_insert()
		with self.assertRaises(frappe.ValidationError):
			change_kind(DOCTYPE, "regular")

	def test_child_to_regular_is_refused_while_a_doctype_uses_it_as_a_table(self):
		change_kind(DOCTYPE, "child")
		table = {"fieldname": "rows", "label": "Rows", "fieldtype": "Table", "options": DOCTYPE}
		make_custom_doctype(PARENT, fields=[table])
		self.addCleanup(delete_committed, "DocType", PARENT)
		with self.assertRaises(frappe.ValidationError):
			change_kind(DOCTYPE, "regular")

	def test_an_empty_doctype_becomes_a_child_table_and_back(self):
		change_kind(DOCTYPE, "child")
		self.assertEqual(frappe.db.get_value("DocType", DOCTYPE, "istable"), 1)
		self.assertTrue(frappe.db.has_column(DOCTYPE, "parent"))

		change_kind(DOCTYPE, "regular")
		self.assertEqual(frappe.db.get_value("DocType", DOCTYPE, "istable"), 0)
		self.assertEqual(frappe.get_all("DocPerm", {"parent": DOCTYPE}, pluck="role"), ["System Manager"])

	def test_submittable_adds_amended_from(self):
		change_kind(DOCTYPE, "submittable")
		self.assertTrue(frappe.get_meta(DOCTYPE).get_field("amended_from"))

	def test_leaving_submittable_drops_submit_cancel_and_amend(self):
		change_kind(DOCTYPE, "submittable")
		doc = frappe.get_doc("DocType", DOCTYPE)
		doc.permissions[0].update({"submit": 1, "cancel": 1, "amend": 1})
		doc.save()
		change_kind(DOCTYPE, "regular")
		rights = frappe.get_doc("DocType", DOCTYPE).permissions[0]
		self.assertEqual((rights.submit, rights.cancel, rights.amend), (0, 0, 0))

	def test_a_user_without_system_manager_is_refused(self):
		make_user(NO_ROLES, [])
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(NO_ROLES)
		with self.assertRaises(frappe.PermissionError):
			change_kind(DOCTYPE, "submittable")

	def test_a_single_cannot_change_kind(self):
		with self.assertRaises(frappe.ValidationError):
			change_kind(DOCTYPE, "single")

	def test_tree_adds_its_fields_and_places_the_records(self):
		record = frappe.get_doc({"doctype": DOCTYPE, "title": "One"}).insert()
		change_kind(DOCTYPE, "tree")
		self.assertEqual(
			frappe.db.get_value("DocType", DOCTYPE, "nsm_parent_field"), "parent_test_editor_47278"
		)
		self.assertEqual(frappe.db.get_value(DOCTYPE, record.name, ["lft", "rgt"]), (1, 2))


class TestRenameDoctype(IntegrationTestCase):
	def setUp(self):
		make_custom_doctype(DOCTYPE)
		self.addCleanup(delete_committed, "DocType", DOCTYPE)
		self.addCleanup(delete_committed, "DocType", RENAMED)

	def test_rename_keeps_the_records(self):
		record = frappe.get_doc({"doctype": DOCTYPE, "title": "One"}).insert()
		self.assertEqual(rename_doctype(DOCTYPE, RENAMED), RENAMED)
		self.assertFalse(frappe.db.exists("DocType", DOCTYPE))
		self.assertEqual(frappe.db.get_value(RENAMED, record.name, "title"), "One")


class TestRenameEffects(IntegrationTestCase):
	def setUp(self):
		make_custom_doctype(DOCTYPE)
		self.addCleanup(delete_committed, "DocType", DOCTYPE)
		self.addCleanup(delete_committed, "DocType", PARENT)

	def test_it_counts_the_link_and_table_fields_that_point_to_it(self):
		self.assertEqual(rename_effects(DOCTYPE), 0)
		fields = [
			{"fieldname": "link", "label": "Link", "fieldtype": "Link", "options": DOCTYPE},
			{"fieldname": "again", "label": "Again", "fieldtype": "Link", "options": DOCTYPE},
			{"fieldname": "other", "label": "Other", "fieldtype": "Link", "options": "User"},
		]
		make_custom_doctype(PARENT, fields=fields)
		self.assertEqual(rename_effects(DOCTYPE), 2)

	def test_it_counts_custom_fields_and_table_fields_but_not_its_own(self):
		make_custom_doctype(DOCTYPE, istable=1)
		make_custom_doctype(
			PARENT, fields=[{"fieldname": "rows", "label": "Rows", "fieldtype": "Table", "options": DOCTYPE}]
		)
		for dt in (PARENT, DOCTYPE):
			field = frappe.get_doc(
				{
					"doctype": "Custom Field",
					"dt": dt,
					"fieldname": "test_47441_link",
					"fieldtype": "Link",
					"options": DOCTYPE,
				}
			).insert()
			self.addCleanup(delete_committed, "Custom Field", field.name)
		self.assertEqual(rename_effects(DOCTYPE), 2)

	def test_it_counts_table_multiselect_fields(self):
		make_custom_doctype(
			DOCTYPE,
			istable=1,
			fields=[{"fieldname": "user", "label": "User", "fieldtype": "Link", "options": "User"}],
		)
		make_custom_doctype(
			PARENT,
			fields=[
				{"fieldname": "users", "label": "Users", "fieldtype": "Table MultiSelect", "options": DOCTYPE}
			],
		)
		self.assertEqual(rename_effects(DOCTYPE), 1)

	def test_it_is_for_a_system_manager(self):
		make_user(NO_ROLES, [])
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(NO_ROLES)
		with self.assertRaises(frappe.PermissionError):
			rename_effects(DOCTYPE)


class TestMoveWithoutDeveloperMode(IntegrationTestCase):
	def setUp(self):
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 0}))
		make_custom_doctype(DOCTYPE)
		self.addCleanup(delete_committed, "DocType", DOCTYPE)
		make_user(SYSTEM_MANAGER, ["System Manager"])
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(SYSTEM_MANAGER)

	def test_a_custom_doctype_moves(self):
		move_doctype(DOCTYPE, "Desk")
		self.assertEqual(frappe.db.get_value("DocType", DOCTYPE, "module"), "Desk")

	def test_a_standard_doctype_does_not(self):
		frappe.db.set_value("DocType", DOCTYPE, "custom", 0)
		with patch("frappe.desk.doctype_editor.danger.move_folder") as move_folder:
			with self.assertRaises(frappe.PermissionError):
				move_doctype(DOCTYPE, "Desk")
		move_folder.assert_not_called()
		self.assertEqual(frappe.db.get_value("DocType", DOCTYPE, "module"), "Custom")


class TestDeleteDoctype(IntegrationTestCase):
	def setUp(self):
		make_custom_doctype(DOCTYPE)
		self.addCleanup(delete_committed, "DocType", DOCTYPE)

	def test_delete_drops_the_table(self):
		frappe.get_doc({"doctype": DOCTYPE, "title": "One"}).insert()
		delete_doctype(DOCTYPE)
		self.assertFalse(frappe.db.exists("DocType", DOCTYPE))
		self.assertFalse(frappe.db.table_exists(DOCTYPE))


def folder(module: str) -> Path:
	return Path(frappe.get_module_path(module, "doctype", frappe.scrub(DOCTYPE)))


def forget_controllers():
	"""Else the next test's new custom DocType imports the deleted standard controller."""
	for name in [name for name in sys.modules if frappe.scrub(DOCTYPE) in name]:
		del sys.modules[name]
	for key in [key for key in doctype_python_modules if key[1] == DOCTYPE]:
		del doctype_python_modules[key]


class TestFiles(IntegrationTestCase):
	"""Make standard and Move write into frappe's own Core and Desk modules; each test removes the files."""

	def setUp(self):
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 1}))
		make_custom_doctype(DOCTYPE)
		self.addCleanup(delete_committed, "DocType", DOCTYPE)
		for module in ("Core", "Desk"):
			self.addCleanup(shutil.rmtree, folder(module), ignore_errors=True)
		self.addCleanup(forget_controllers)

	def test_make_standard_writes_the_files(self):
		make_standard(DOCTYPE, "Core")
		self.assertEqual(frappe.db.get_value("DocType", DOCTYPE, ["custom", "module"]), (0, "Core"))
		self.assertTrue((folder("Core") / "test_editor_47278.json").exists())

	def test_make_standard_needs_developer_mode(self):
		frappe.conf.developer_mode = 0
		with self.assertRaises(frappe.PermissionError):
			make_standard(DOCTYPE, "Core")

	def test_make_standard_is_refused_into_a_module_that_has_its_folder(self):
		folder("Core").mkdir(parents=True)
		with self.assertRaises(frappe.ValidationError):
			make_standard(DOCTYPE, "Core")
		self.assertEqual(frappe.db.get_value("DocType", DOCTYPE, "custom"), 1)

	def test_a_standard_doctype_without_a_tree_controller_cannot_become_a_tree(self):
		make_standard(DOCTYPE, "Core")
		with self.assertRaises(frappe.ValidationError):
			change_kind(DOCTYPE, "tree")

	def test_only_administrator_renames_or_deletes_a_standard_doctype(self):
		make_standard(DOCTYPE, "Core")
		make_user(SYSTEM_MANAGER, ["System Manager"])
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(SYSTEM_MANAGER)
		with self.assertRaises(frappe.PermissionError):
			rename_doctype(DOCTYPE, RENAMED)
		with self.assertRaises(frappe.PermissionError):
			delete_doctype(DOCTYPE)
		self.assertTrue(frappe.db.exists("DocType", DOCTYPE))

	def test_a_system_manager_moves_a_standard_doctype(self):
		make_standard(DOCTYPE, "Core")
		make_user(SYSTEM_MANAGER, ["System Manager"])
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(SYSTEM_MANAGER)
		move_doctype(DOCTYPE, "Desk")
		self.assertEqual(frappe.db.get_value("DocType", DOCTYPE, "module"), "Desk")

	def test_move_moves_the_files(self):
		make_standard(DOCTYPE, "Core")
		move_doctype(DOCTYPE, "Desk")
		self.assertEqual(frappe.db.get_value("DocType", DOCTYPE, "module"), "Desk")
		self.assertFalse(folder("Core").exists())
		self.assertTrue((folder("Desk") / "test_editor_47278.json").exists())
		self.assertTrue((folder("Desk") / "test_editor_47278.py").exists())

	def test_move_is_refused_into_a_module_that_has_its_folder(self):
		make_standard(DOCTYPE, "Core")
		folder("Desk").mkdir(parents=True)
		with self.assertRaises(frappe.ValidationError):
			move_doctype(DOCTYPE, "Desk")
		self.assertTrue((folder("Core") / "test_editor_47278.json").exists())

	def test_move_is_refused_while_other_code_imports_from_its_folder(self):
		make_standard(DOCTYPE, "Core")
		caller = Path(frappe.get_app_path("frappe", "desk", "test_editor_47278_caller.py"))
		# Joined here, so this file does not name the path itself.
		path = ".".join(("frappe.core.doctype", "test_editor_47278", "test_editor_47278"))
		caller.write_text(f"from {path} import TestEditor47278\n")
		self.addCleanup(caller.unlink)
		with self.assertRaises(frappe.ValidationError) as refused:
			move_doctype(DOCTYPE, "Desk")
		self.assertIn("test_editor_47278_caller.py", str(refused.exception))
		self.assertTrue((folder("Core") / "test_editor_47278.json").exists())

	def test_a_failed_save_moves_the_folder_back(self):
		make_standard(DOCTYPE, "Core")
		with patch("frappe.core.doctype.doctype.doctype.DocType.save", side_effect=frappe.ValidationError):
			with self.assertRaises(frappe.ValidationError):
				move_doctype(DOCTYPE, "Desk")
		self.assertTrue((folder("Core") / "test_editor_47278.json").exists())
		self.assertFalse(folder("Desk").exists())
