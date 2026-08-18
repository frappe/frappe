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

	def test_csv_delimiter_fields_depends_on(self):
		frappe.reload_doc("core", "doctype", "data_import")
		meta = frappe.get_meta("Data Import")
		self.assertEqual(meta.get_field("use_csv_sniffer").depends_on, CSV_IMPORT_SOURCE_DEPENDS_ON)
		self.assertEqual(meta.get_field("custom_delimiters").depends_on, CSV_IMPORT_SOURCE_DEPENDS_ON)
		self.assertEqual(meta.get_field("delimiter_options").depends_on, CSV_DELIMITER_OPTIONS_DEPENDS_ON)
