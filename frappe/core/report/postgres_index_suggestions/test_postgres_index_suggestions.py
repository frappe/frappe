# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from unittest.mock import Mock, patch

from psycopg2.errors import InsufficientPrivilege

import frappe
from frappe.core.report.postgres_index_suggestions.postgres_index_suggestions import (
	_leading_indexed_columns,
	_suggested_columns,
)
from frappe.query_builder.utils import db_type_is
from frappe.tests import IntegrationTestCase
from frappe.tests.test_query_builder import run_only_if


@run_only_if(db_type_is.POSTGRES)
class TestPostgresIndexSuggestions(IntegrationTestCase):
	def replace_statements_read(self, read):
		"""Call `read` in place of the pg_stat_statements query."""
		real_sql = frappe.db.sql

		def sql(query, *args, **kwargs):
			return read() if "pg_stat_statements" in str(query) else real_sql(query, *args, **kwargs)

		self.enterContext(patch.object(frappe.db, "sql", sql))

	def test_missing_extension_keeps_earlier_work(self):
		todo = frappe.get_doc(doctype="ToDo", description="Index suggestions").insert()
		# a real missing relation, so the transaction aborts as it does on the server
		self.replace_statements_read(
			lambda: frappe.db._cursor.execute("SELECT 1 FROM pg_stat_statements_missing")
		)

		self.assertEqual(_suggested_columns({"tabToDo"}), {})
		self.assertTrue(frappe.db.exists("ToDo", todo.name))

	def test_unrelated_failure_is_reraised(self):
		self.replace_statements_read(Mock(side_effect=InsufficientPrivilege("permission denied")))

		with self.assertRaises(InsufficientPrivilege):
			_suggested_columns({"tabToDo"})

	def test_indexes_come_from_the_site_schema_only(self):
		indexed = _leading_indexed_columns({"tabToDo", "pg_class"})

		self.assertIn("name", indexed["tabToDo"])
		# pg_class is indexed in pg_catalog, not in the site schema
		self.assertNotIn("pg_class", indexed)
