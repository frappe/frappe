# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.core.report.database_storage_usage_by_tables.database_storage_usage_by_tables import (
	execute,
)
from frappe.tests import IntegrationTestCase
from frappe.tests.test_query_builder import db_type_is, run_only_if


class TestDBUsageReport(IntegrationTestCase):
	def test_basic_query(self):
		_, data = execute()
		tables = [d.table for d in data]
		self.assertFalse({"tabUser", "tabDocField"}.difference(tables))

	@run_only_if(db_type_is.SQLITE)
	def test_sqlite_size_uses_dbstat_bytes(self):
		_, data = execute()
		reported = {row.table: row for row in data}["tabDocField"]
		data_bytes, index_bytes = frappe.db.sql(
			"""SELECT
				COALESCE(SUM(CASE WHEN objects.type = 'table' THEN pages.pgsize ELSE 0 END), 0),
				COALESCE(SUM(CASE WHEN objects.type = 'index' THEN pages.pgsize ELSE 0 END), 0)
			FROM dbstat AS pages
			JOIN sqlite_master AS objects ON objects.name = pages.name
			WHERE objects.tbl_name = 'tabDocField'"""
		)[0]

		mebibyte = 1024 * 1024
		# The report rounds in SQLite. Compare it with the exact byte count within
		# half of the displayed 0.01 MiB precision instead of relying on Python's
		# different tie-breaking rule for round().
		maximum_rounding_error = 0.0051
		self.assertAlmostEqual(reported.data_size, data_bytes / mebibyte, delta=maximum_rounding_error)
		self.assertAlmostEqual(reported.index_size, index_bytes / mebibyte, delta=maximum_rounding_error)
		self.assertAlmostEqual(
			reported.size,
			(data_bytes + index_bytes) / mebibyte,
			delta=maximum_rounding_error,
		)
