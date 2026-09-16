# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import unittest
from contextlib import suppress

from psycopg2.errors import ObjectNotInPrerequisiteState

import frappe
from frappe.core.report.postgres_query_stats.postgres_query_stats import get_query_stats
from frappe.tests import IntegrationTestCase

STATS_TABLE = "pg_stat_statements s"


@unittest.skipUnless(frappe.db.db_type == "postgres", "pg_stat_statements is PostgreSQL only")
class TestPostgresQueryStats(IntegrationTestCase):
	def fail_stats_query(self, exception: Exception):
		"""Stand in for PostgreSQL: abort the transaction for real, then raise `exception`."""
		real_sql = frappe.db.sql

		def sql(query, *args, **kwargs):
			if STATS_TABLE not in str(query):
				return real_sql(query, *args, **kwargs)
			# abort the transaction through the driver, skipping frappe's query error logging
			with suppress(Exception):
				frappe.db._cursor.execute("SELECT 1 FROM pg_stat_statements_not_loaded")
			raise exception

		frappe.db.sql = sql
		self.addCleanup(lambda: delattr(frappe.db, "sql"))

	def test_preload_library_missing_names_the_setup_step(self):
		self.fail_stats_query(ObjectNotInPrerequisiteState("pg_stat_statements must be loaded"))

		with self.assertRaises(frappe.ValidationError) as raised:
			get_query_stats(50)

		self.assertIn("shared_preload_libraries", str(raised.exception))
		# the savepoint rollback must leave the connection usable for the rest of the request
		self.assertEqual(frappe.db.sql("SELECT 1")[0][0], 1)

	def test_unrelated_failure_is_reraised(self):
		self.fail_stats_query(RuntimeError("connection reset"))

		with self.assertRaises(RuntimeError):
			get_query_stats(50)
