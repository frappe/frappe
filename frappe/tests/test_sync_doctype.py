# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import shutil
import sys
from pathlib import Path

import frappe
from frappe.modules.sync_doctype import DocTypeSyncError, sync_doctype_from_file
from frappe.tests import IntegrationTestCase

DOCTYPE_NAME = "Test Sync Agent DocType"
SCRUBBED = "test_sync_agent_doctype"


def make_definition(**overrides):
	definition = {
		"doctype": "DocType",
		"name": DOCTYPE_NAME,
		"module": "Core",
		"custom": 0,
		"fields": [{"fieldname": "field_1", "fieldtype": "Data", "label": "Field 1"}],
		"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}],
		"sort_field": "creation",
		"sort_order": "DESC",
	}
	definition.update(overrides)
	return definition


class TestSyncDoctype(IntegrationTestCase):
	def setUp(self):
		self._developer_mode = frappe.conf.developer_mode
		frappe.conf.developer_mode = 1
		self.folder = Path(frappe.get_app_path("frappe", "core", "doctype", SCRUBBED))
		self.path = self.folder / f"{SCRUBBED}.json"

	def tearDown(self):
		frappe.db.rollback()
		if frappe.db.exists("DocType", DOCTYPE_NAME):
			frappe.delete_doc("DocType", DOCTYPE_NAME, force=1)
		frappe.db.commit()
		frappe.conf.developer_mode = self._developer_mode
		shutil.rmtree(self.folder, ignore_errors=True)

		# purge module caches so the deleted controller stub isn't found by the next test
		from frappe.modules.utils import doctype_python_modules

		for key in [k for k in sys.modules if SCRUBBED in k]:
			del sys.modules[key]
		for key in [k for k in doctype_python_modules if k[1] == DOCTYPE_NAME]:
			del doctype_python_modules[key]
		frappe.controllers.get(frappe.local.site, {}).pop(DOCTYPE_NAME, None)

	def write_definition(self, definition):
		self.folder.mkdir(parents=True, exist_ok=True)
		self.path.write_text(frappe.as_json(definition) + "\n")

	def test_requires_developer_mode(self):
		frappe.conf.developer_mode = 0
		self.write_definition(make_definition())
		self.assertRaises(DocTypeSyncError, sync_doctype_from_file, str(self.path))

	def test_creates_new_doctype_and_renormalizes(self):
		self.write_definition(make_definition())
		result = sync_doctype_from_file(str(self.path))

		self.assertTrue(frappe.db.exists("DocType", DOCTYPE_NAME))
		self.assertTrue(frappe.db.has_column(DOCTYPE_NAME, "field_1"))

		# the save re-exported the file, renormalizing the sparse hand-written JSON
		self.assertTrue(result["renormalized"])
		exported = frappe.get_file_json(self.path)
		self.assertEqual(exported["field_order"], ["field_1"])
		self.assertTrue(exported["modified"])

		# controller stub generated
		self.assertTrue((self.folder / f"{SCRUBBED}.py").is_file())
		self.assertTrue((self.folder / "__init__.py").is_file())

	def test_update_by_name_and_rename_warning(self):
		self.write_definition(make_definition())
		sync_doctype_from_file(str(self.path))

		exported = frappe.get_file_json(self.path)
		exported["fields"] = [{"fieldname": "field_one", "fieldtype": "Data", "label": "Field One"}]
		exported["field_order"] = ["field_one"]
		self.write_definition(exported)

		# a name (not a path) resolves to the canonical export path
		result = sync_doctype_from_file(DOCTYPE_NAME)

		self.assertTrue(frappe.db.has_column(DOCTYPE_NAME, "field_one"))
		self.assertEqual(len(result["warnings"]), 1)
		self.assertIn("field_1", result["warnings"][0])
		self.assertIn("field_one", result["warnings"][0])

	def test_validation_failure_saves_nothing(self):
		definition = make_definition(
			fields=[
				{"fieldname": "dup", "fieldtype": "Data", "label": "Dup"},
				{"fieldname": "dup", "fieldtype": "Data", "label": "Dup 2"},
			]
		)
		self.write_definition(definition)

		self.assertRaises(Exception, sync_doctype_from_file, str(self.path))
		self.assertFalse(frappe.db.exists("DocType", DOCTYPE_NAME))
		# file left as written for the agent to fix
		self.assertEqual(frappe.get_file_json(self.path), definition)

	def test_path_mismatch_guard(self):
		wrong_folder = Path(frappe.get_app_path("frappe", "core", "doctype", "wrong_location"))
		wrong_folder.mkdir(parents=True, exist_ok=True)
		self.addCleanup(shutil.rmtree, wrong_folder, ignore_errors=True)
		wrong_path = wrong_folder / f"{SCRUBBED}.json"
		wrong_path.write_text(frappe.as_json(make_definition()) + "\n")

		self.assertRaises(DocTypeSyncError, sync_doctype_from_file, str(wrong_path))

	def test_unknown_module_guard(self):
		self.write_definition(make_definition(module="No Such Module"))
		self.assertRaises(Exception, sync_doctype_from_file, str(self.path))

	def test_custom_doctype_refused(self):
		self.write_definition(make_definition(custom=1))
		self.assertRaises(DocTypeSyncError, sync_doctype_from_file, str(self.path))
