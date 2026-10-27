# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.core.doctype.data_import.data_import import form_start_import
from frappe.core.doctype.data_import.importer import Column
from frappe.handler import run_doc_method
from frappe.tests import IntegrationTestCase, UnitTestCase

# Keep in sync with depends_on on use_csv_sniffer / custom_delimiters in data_import.json
CSV_IMPORT_SOURCE_DEPENDS_ON = "eval:doc.google_sheets_url || (doc.import_file && doc.import_file.split('.').pop().toLowerCase() === 'csv')"
CSV_DELIMITER_OPTIONS_DEPENDS_ON = "eval:doc.custom_delimiters && (doc.google_sheets_url || (doc.import_file && doc.import_file.split('.').pop().toLowerCase() === 'csv'))"


def is_csv_import_source(import_file: str | None = None, google_sheets_url: str | None = None) -> bool:
	"""Whether CSV delimiter / sniffer settings apply to the current import source."""
	if google_sheets_url:
		return True
	if not import_file:
		return False
	return import_file.rsplit(".", 1)[-1].lower() == "csv"


class TestDataImport(UnitTestCase):
	def test_is_csv_import_source(self):
		self.assertFalse(is_csv_import_source())
		self.assertFalse(is_csv_import_source(import_file="/files/sample.xlsx"))
		self.assertFalse(is_csv_import_source(import_file="/files/sample.xls"))
		self.assertTrue(is_csv_import_source(import_file="/files/sample.csv"))
		self.assertTrue(is_csv_import_source(import_file="/files/sample.CSV"))
		self.assertTrue(
			is_csv_import_source(google_sheets_url="https://docs.google.com/spreadsheets/d/abc/edit")
		)
		self.assertTrue(
			is_csv_import_source(
				import_file="/files/sample.xlsx",
				google_sheets_url="https://docs.google.com/spreadsheets/d/abc/edit",
			)
		)

	def test_explicit_column_mapping_does_not_emit_mapping_info_warning(self):
		col = Column(0, "Col Header", "User", ["test@example.com"], map_to_field="Email")
		self.assertTrue(col.df)
		self.assertFalse(any("Mapping column" in w.get("message", "") for w in col.warnings))

	def test_invalid_column_mapping_still_warns(self):
		col = Column(0, "Col Header", "User", ["test@example.com"], map_to_field="Nonexistent Field")
		self.assertTrue(any("Could not map column" in w.get("message", "") for w in col.warnings))

	def test_column_mapping_warning_escapes_the_field_name(self):
		col = Column(0, "Col Header", "User", ["x"], map_to_field="<img src=x onerror=alert(1)>")
		message = next(w["message"] for w in col.warnings if "Could not map column" in w["message"])
		self.assertNotIn("<img", message)
		self.assertIn("&lt;img", message)

	def test_clear_stale_template_warnings_on_file_swap(self):
		"""Swapping import_file must drop blocked-import snapshots (wizard routing)."""
		import json

		di = frappe.new_doc("Data Import")
		di.reference_doctype = "User"
		di.import_type = "Insert New Records"
		di.import_file = "/files/old.csv"
		di.template_warnings = json.dumps([{"message": "stale blocked import", "row": 1}])

		before = frappe.new_doc("Data Import")
		before.reference_doctype = "User"
		before.import_type = "Insert New Records"
		before.import_file = "/files/old.csv"
		before.template_warnings = di.template_warnings

		di.import_file = "/files/new.csv"
		di.clear_stale_template_warnings(before)
		self.assertFalse(di.template_warnings)

	def test_clear_stale_template_warnings_keeps_on_skip_only(self):
		"""skipped_rows-only edits must keep template_warnings for Undo Skip UI."""
		import json

		di = frappe.new_doc("Data Import")
		di.reference_doctype = "User"
		di.import_type = "Insert New Records"
		di.import_file = "/files/sample.csv"
		di.template_warnings = json.dumps([{"message": "blocked", "row": 2}])
		before = frappe.new_doc("Data Import")
		before.reference_doctype = "User"
		before.import_type = "Insert New Records"
		before.import_file = "/files/sample.csv"
		before.template_warnings = di.template_warnings
		before.append("skipped_rows", {"row_number": 2})

		# Same source + mappings; only skipped_rows differ on `before` vs current empty skips.
		di.clear_stale_template_warnings(before)
		self.assertTrue(di.template_warnings)

	def test_csv_delimiter_fields_depends_on(self):
		frappe.reload_doc("core", "doctype", "data_import")
		meta = frappe.get_meta("Data Import")
		self.assertEqual(meta.get_field("use_csv_sniffer").depends_on, CSV_IMPORT_SOURCE_DEPENDS_ON)
		self.assertEqual(meta.get_field("custom_delimiters").depends_on, CSV_IMPORT_SOURCE_DEPENDS_ON)
		self.assertEqual(meta.get_field("delimiter_options").depends_on, CSV_DELIMITER_OPTIONS_DEPENDS_ON)


class TestDataImportStartPermission(IntegrationTestCase):
	READER = "data-import-reader@example.com"
	WRITER = "data-import-writer@example.com"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.data_import = frappe.get_doc(
			{"doctype": "Data Import", "reference_doctype": "User", "import_type": "Insert New Records"}
		).insert()
		for email, write in ((cls.READER, 0), (cls.WRITER, 1)):
			frappe.get_doc(doctype="User", email=email, first_name=email, send_welcome_email=0).insert(
				ignore_if_duplicate=True
			)
			frappe.share.add("Data Import", cls.data_import.name, email, read=1, write=write)

	def setUp(self):
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		frappe.local.request = frappe._dict(method="POST")
		self.addCleanup(frappe.set_user, "Administrator")

	def test_run_doc_method_refuses_a_reader(self):
		frappe.set_user(self.READER)
		with patch("frappe.core.doctype.data_import.data_import.enqueue") as enqueue:
			self.assertRaises(frappe.PermissionError, self.run_start_import)
		enqueue.assert_not_called()

	def test_run_doc_method_starts_the_import_for_a_writer(self):
		frappe.set_user(self.WRITER)
		with patch("frappe.core.doctype.data_import.data_import.enqueue") as enqueue:
			self.run_start_import()
		enqueue.assert_called_once()
		self.assertTrue(frappe.response["message"])

	def test_form_start_import_checks_write(self):
		frappe.set_user(self.READER)
		self.assertRaises(frappe.PermissionError, form_start_import, self.data_import.name)

		frappe.set_user(self.WRITER)
		with patch("frappe.core.doctype.data_import.data_import.enqueue") as enqueue:
			self.assertTrue(form_start_import(self.data_import.name))
		enqueue.assert_called_once()

	def run_start_import(self):
		run_doc_method("start_import", dt="Data Import", dn=self.data_import.name)
