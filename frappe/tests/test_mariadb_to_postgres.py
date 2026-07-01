# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import gzip
import os
import tempfile
from unittest.mock import patch

import frappe
from frappe.database.postgres import import_from_mariadb as converter
from frappe.installer import get_dump_db_type
from frappe.tests import UnitTestCase

MARIADB_DUMP_HEADER = (
	"-- begin frappe metadata\n-- version = 15.0.0\n-- end frappe metadata\n"
	"/*!40101 SET NAMES utf8mb4 */;\n-- MariaDB dump 10.19\n"
	"CREATE TABLE `tabUser` (\n  `name` varchar(140) NOT NULL\n);\n"
)
POSTGRES_DUMP_HEADER = (
	"-- begin frappe metadata\n-- version = 15.0.0\n-- end frappe metadata\n"
	"--\n-- PostgreSQL database dump\n--\n"
	'CREATE TABLE public."tabUser" (\n  "name" varchar(140) NOT NULL\n);\n'
)


def _write_dump(text: str, suffix: str) -> str:
	fd, path = tempfile.mkstemp(suffix=suffix)
	os.close(fd)
	opener = gzip.open if suffix.endswith(".gz") else open
	with opener(path, "wt") as f:
		f.write(text)
	return path


class TestMariaDBToPostgres(UnitTestCase):
	def test_detects_dump_engine(self):
		for suffix in (".sql", ".sql.gz"):
			maria = _write_dump(MARIADB_DUMP_HEADER, suffix)
			postgres = _write_dump(POSTGRES_DUMP_HEADER, suffix)
			self.addCleanup(os.unlink, maria)
			self.addCleanup(os.unlink, postgres)
			self.assertEqual(get_dump_db_type(maria), "mariadb")
			self.assertEqual(get_dump_db_type(postgres), "postgres")

	def test_arm_is_unsupported(self):
		with patch("platform.machine", return_value="arm64"):
			self.assertRaises(frappe.ValidationError, converter.assert_conversion_supported)

	def test_missing_pgloader_is_reported(self):
		with (
			patch("platform.machine", return_value="x86_64"),
			patch.object(converter, "which", return_value=None),
		):
			self.assertRaises(frappe.ExecutableNotFound, converter.assert_conversion_supported)

	def test_pgloader_command_uses_frappe_conventions(self):
		command = converter.build_pgloader_command(
			"srcdb",
			{"host": "mh", "port": "3306", "user": "root", "password": "p@s s"},
			{"host": "ph", "port": "5432", "user": "u", "password": "pw"},
			"targetdb",
		)
		self.assertIn("quote identifiers", command)
		# migrate owns the secondary indexes; pgloader must not also copy them (double indexes)
		self.assertIn("create no indexes", command)
		self.assertIn("ALTER SCHEMA 'srcdb' RENAME TO 'public'", command)
		self.assertIn("type tinyint to smallint drop typemod", command)
		self.assertIn("type decimal to numeric keep typemod", command)
		# credentials are URL-encoded into the connection URIs
		self.assertIn("mysql://root:p%40s%20s@mh:3306/srcdb", command)
		self.assertIn("postgresql://u:pw@ph:5432/targetdb", command)

	def _converter(self, **kwargs):
		return converter.MariaDBToPostgres(
			"/x.sql.gz",
			{"host": "h", "port": "3306", "user": "root", "password": ""},
			{"host": "ph", "port": "5432", "user": "u", "password": "pw", "db_name": "db"},
			**kwargs,
		)

	def test_dynamic_space_omitted_by_default(self):
		conv = self._converter()
		self.assertIsNone(conv.dynamic_space_mb)
		with patch.object(converter, "execute_in_shell") as run:
			conv._run_pgloader()
		self.assertNotIn("--dynamic-space-size", run.call_args.args[0])

	def test_pgloader_run_uses_configured_dynamic_space(self):
		conv = self._converter(dynamic_space_mb=9000)
		with patch.object(converter, "execute_in_shell") as run:
			conv._run_pgloader()
		self.assertIn("--dynamic-space-size 9000", run.call_args.args[0])

	def test_staging_database_identifier_is_backtick_quoted(self):
		self.assertEqual(converter._mysql_identifier("my-db"), "`my-db`")
		self.assertEqual(converter._mysql_identifier("a`b"), "`a``b`")
		conv = self._converter(staging_db="my-db")
		with patch.object(converter, "execute_in_shell") as run:
			conv._stage_dump_in_mariadb()
		self.assertIn("CREATE DATABASE `my-db`", run.call_args_list[0].args[0])

	def test_pg_dump_command_aborts_on_header_failure(self):
		target = {"host": "h", "port": "5432", "user": "u", "password": "pw", "db_name": "db"}
		with (
			patch.object(converter, "_frappe_metadata_header", return_value="-- hdr\n"),
			patch.object(converter, "execute_in_shell") as run,
		):
			converter._pg_dump_to_file(target, "/tmp/out.sql.gz", "/src.sql.gz")
		# header write and pg_dump are &&-chained so a failed header aborts the dump
		self.assertIn(" && ", run.call_args.args[0])
		self.assertNotIn("; ", run.call_args.args[0])
