# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from contextlib import closing
from datetime import date
from unittest.mock import patch

import frappe
from frappe.core.doctype.duckdb_sync.duckdb_sync import (
	get_attach_query,
	is_data_sync_pending,
	sync_data_to_duckdb,
)
from frappe.database import delete_duckdb_file, get_duckdb
from frappe.tests import IntegrationTestCase, UnitTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = ["User"]

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
	def setUp(self):
		super().setUp()
		self.enterContext(self.set_user("test@example.com"))
		self.todos = []
		self.sync = None
		self.schema_created = False
		self.addCleanup(self.cleanup_sync)
		for status, priority in (("Open", "High"), ("Closed", "Low")):
			self.todos.append(
				frappe.get_doc(
					doctype="ToDo",
					description=f"DuckDB {status}: café, 'quotes', and \\slashes at example.com",
					status=status,
					priority=priority,
					date=date(2026, 1, 2),
				).insert()
			)
		# The scanner uses a separate connection and cannot read uncommitted fixtures.
		frappe.db.commit()
		self.expected_rows = [
			(todo.name, todo.description, todo.status, todo.priority, date(2026, 1, 2), todo.owner)
			for todo in self.todos
		]

	def test_extension_sync_copies_rows_and_marks_completion(self):
		self.create_sync()
		self.assert_synced_rows(self.expected_rows)

	def test_postgres_extension_reads_the_configured_schema(self):
		if frappe.db.db_type != "postgres":
			self.skipTest("PostgreSQL schemas are not available on MariaDB")

		from psycopg2 import sql

		frappe.db.sql("CREATE SCHEMA duckdb_sync_test")
		self.schema_created = True
		frappe.db.sql(
			sql.SQL('CREATE TABLE duckdb_sync_test."tabToDo" AS TABLE {}."tabToDo"')
			.format(sql.Identifier(frappe.db.db_schema))
			.as_string(frappe.db._conn)
		)
		frappe.db.sql(
			'UPDATE duckdb_sync_test."tabToDo" SET description = %s WHERE name = %s',
			("Only in the configured schema", self.todos[0].name),
		)
		frappe.db.commit()

		expected_rows = [
			(self.todos[0].name, "Only in the configured schema", *self.expected_rows[0][2:]),
			self.expected_rows[1],
		]
		self.create_sync()
		with patch.dict(frappe.conf, {"db_schema": "duckdb_sync_test"}):
			self.assert_synced_rows(expected_rows)

	def create_sync(self):
		settings = frappe.get_doc("System Settings")
		settings.sync_in_batch = 0
		settings.save()
		self.sync = frappe.get_doc(doctype="DuckDB Sync", doc_type="ToDo").insert()
		self.sync.sync_schema()
		self.assertTrue(is_data_sync_pending(self.sync.name))

	def assert_synced_rows(self, expected_rows):
		with patch("frappe.enqueue"):
			sync_data_to_duckdb(self.sync.name)

		self.assertFalse(is_data_sync_pending(self.sync.name))
		with closing(get_duckdb(filename=self.sync.filename)) as connection:
			rows = connection.execute(
				'FROM "tabToDo" SELECT name, description, status, priority, date, owner WHERE name IN (?, ?)',
				[todo.name for todo in self.todos],
			).fetchall()
			self.assertCountEqual(rows, expected_rows)
			self.assertEqual(
				connection.sql('SELECT count(*) FROM "tabToDo"').fetchone()[0], frappe.db.count("ToDo")
			)

	def cleanup_sync(self):
		frappe.db.rollback()
		if self.sync:
			delete_duckdb_file(self.sync.filename)
		if self.schema_created:
			frappe.db.sql("DROP SCHEMA IF EXISTS duckdb_sync_test CASCADE")
		for todo in self.todos:
			frappe.delete_doc("ToDo", todo.name, delete_permanently=True)
		frappe.db.commit()
