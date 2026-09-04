# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.core.doctype.data_import.importer import Column
from frappe.tests import UnitTestCase

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

	def test_preview_cache_skips_google_sheets(self):
		from frappe.core.doctype.data_import.preview_cache import should_cache_preview

		doc = frappe._dict(
			name="DI-TEST",
			import_file="/files/sample.csv",
			google_sheets_url=None,
		)
		self.assertTrue(should_cache_preview(doc))

		doc.google_sheets_url = "https://docs.google.com/spreadsheets/d/abc/edit"
		self.assertFalse(should_cache_preview(doc))

		doc.import_file = None
		self.assertFalse(should_cache_preview(doc))

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
