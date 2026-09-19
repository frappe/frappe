# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.core.doctype.duckdb_sync.duckdb_sync import (
	DuckDBSync,
	get_attach_query,
	is_data_sync_pending,
	sync_data_to_duckdb,
)
from frappe.tests import IntegrationTestCase, UnitTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = ["Role", "User"]

SITE_CONFIG = {
	"db_user": "site_user",
	"db_password": "pa'ss\"w\\ord",
	"db_host": "db.example.com",
	"db_name": "site_db",
	"db_port": 6000,
}


def read_dsn(query):
	"""The connection string the scanner receives, after SQL undoes its own quoting."""
	literal = query[query.index("'") + 1 : query.rindex("' as ")]
	return literal.replace("''", "'")


def read_dsn_value(dsn, key, quote):
	"""One value the scanner reads back, after it undoes the backslash escapes."""
	characters = iter(dsn[dsn.index(f"{key}={quote}") + len(key) + 2 :])
	value = ""
	for character in characters:
		if character == quote:
			return value
		value += next(characters) if character == "\\" else character
	raise ValueError(f"{key} is not terminated")


class UnitTestDuckDBSync(UnitTestCase):
	def get_query(self, db_type, db_schema="public", **overrides):
		conf = frappe._dict({**SITE_CONFIG, **overrides})
		database = frappe._dict(db_type=db_type, db_schema=db_schema)
		with patch.object(frappe.local, "conf", conf), patch.object(frappe.local, "db", database):
			return get_attach_query()

	def test_postgres_uses_its_own_scanner_and_the_site_schema(self):
		query = self.get_query("postgres", db_schema="alt_schema")
		dsn = read_dsn(query)

		self.assertIn("(TYPE postgres, SCHEMA 'alt_schema')", query)
		self.assertIn("dbname='site_db'", dsn)
		self.assertIn("port='6000'", dsn)

	def test_mariadb_uses_the_mysql_scanner_with_double_quoted_values(self):
		query = self.get_query("mariadb")
		dsn = read_dsn(query)

		self.assertIn("(TYPE mysql)", query)
		self.assertNotIn("SCHEMA", query)
		self.assertIn('database="site_db"', dsn)
		# The MySQL scanner keeps a single quote in the value and cannot read the port.
		self.assertIn('port="6000"', dsn)

	def test_credentials_survive_the_scanner_and_sql_quoting(self):
		for db_type, quote in (("postgres", "'"), ("mariadb", '"')):
			with self.subTest(db_type=db_type):
				dsn = read_dsn(self.get_query(db_type))
				self.assertEqual(read_dsn_value(dsn, "password", quote), SITE_CONFIG["db_password"])
				self.assertEqual(read_dsn_value(dsn, "user", quote), SITE_CONFIG["db_user"])

	def test_host_port_and_user_fall_back(self):
		dsn = read_dsn(self.get_query("postgres", db_host=None, db_port=None, db_user=None))

		self.assertIn("host='127.0.0.1'", dsn)
		self.assertIn("port='5432'", dsn)
		self.assertIn("user='site_db'", dsn)


class IntegrationTestDuckDBSync(IntegrationTestCase):
	def test_extension_sync_copies_rows_and_marks_completion(self):
		import duckdb

		with self.set_user("test@example.com"), duckdb.connect(":memory:") as connection:
			expected_rows = frappe.get_list(
				"Role",
				filters={"name": ["in", ["_Test Role", "_Test Role 4"]]},
				fields=["name", "role_name", "desk_access", "disabled", "creation", "owner"],
				as_list=True,
			)
			self.assertEqual(len(expected_rows), 2)
			settings = frappe.get_doc("System Settings")
			settings.sync_in_batch = 0
			settings.save()
			sync = frappe.get_doc(doctype="DuckDB Sync", doc_type="Role").insert()

			# Cursors share the in-memory database and let the sync close its own connection.
			with patch.object(DuckDBSync, "get_duckdb_conn", side_effect=connection.cursor):
				sync.sync_schema()
				self.assertTrue(is_data_sync_pending(sync.name))
				with patch("frappe.enqueue"):
					sync_data_to_duckdb(sync.name)

			self.assertFalse(is_data_sync_pending(sync.name))
			rows = connection.execute(
				'FROM "tabRole" SELECT name, role_name, desk_access, disabled, creation, owner '
				"WHERE name IN (?, ?)",
				["_Test Role", "_Test Role 4"],
			).fetchall()
			self.assertCountEqual(rows, expected_rows)
			self.assertEqual(
				connection.sql('SELECT count(*) FROM "tabRole"').fetchone()[0], frappe.db.count("Role")
			)

	def test_postgres_extension_reads_the_configured_schema(self):
		if frappe.db.db_type != "postgres":
			self.skipTest("PostgreSQL schemas are not available on MariaDB")

		import duckdb

		with (
			self.set_user("test@example.com"),
			duckdb.connect(":memory:") as connection,
			patch.dict(frappe.conf, {"db_schema": "pg_catalog"}),
		):
			connection.sql(get_attach_query())
			rows = connection.sql(
				"SELECT nspname FROM source_db.pg_namespace WHERE nspname = 'pg_catalog'"
			).fetchall()
			self.assertEqual(rows, [("pg_catalog",)])
