# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.core.doctype.duckdb_sync.duckdb_sync import get_attach_query
from frappe.tests import IntegrationTestCase, UnitTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]

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
	"""
	Integration tests for DuckDBSync.
	Use this class for testing interactions between multiple components.
	"""

	pass
