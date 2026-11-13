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
)
from frappe.desk.doctype_editor.test_save_design import delete_committed, make_custom_doctype
from frappe.modules.utils import doctype_python_modules
from frappe.tests import IntegrationTestCase

DOCTYPE = "Test Editor 47278"
RENAMED = "Test Editor 47278 Renamed"


class TestChangeKind(IntegrationTestCase):
	def setUp(self):
		make_custom_doctype(DOCTYPE)
		self.addCleanup(delete_committed, "DocType", DOCTYPE)

	def test_regular_to_child_is_refused_while_records_exist(self):
		frappe.get_doc({"doctype": DOCTYPE, "title": "One"}).insert()
		with self.assertRaises(frappe.ValidationError):
			change_kind(DOCTYPE, "child")
		self.assertEqual(frappe.db.get_value("DocType", DOCTYPE, "istable"), 0)

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

	def test_a_single_cannot_change_kind(self):
		with self.assertRaises(frappe.ValidationError):
			change_kind(DOCTYPE, "single")

	def test_tree_adds_its_fields_and_places_the_records(self):
		record = frappe.get_doc({"doctype": DOCTYPE, "title": "One"}).insert()
		change_kind(DOCTYPE, "tree")
		self.assertEqual(frappe.db.get_value("DocType", DOCTYPE, "nsm_parent_field"), "parent_test_editor_47278")
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

	def test_move_moves_the_files(self):
		make_standard(DOCTYPE, "Core")
		move_doctype(DOCTYPE, "Desk")
		self.assertEqual(frappe.db.get_value("DocType", DOCTYPE, "module"), "Desk")
		self.assertFalse(folder("Core").exists())
		self.assertTrue((folder("Desk") / "test_editor_47278.json").exists())
		self.assertTrue((folder("Desk") / "test_editor_47278.py").exists())
