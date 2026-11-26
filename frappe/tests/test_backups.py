import contextlib
import gzip
import os
import re
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import frappe
from frappe.database.sqlite.mariadb_dump import (
	Column,
	MariaDBDumpError,
	MariaDBDumpWriter,
	parse_table_shape,
)
from frappe.tests import IntegrationTestCase
from frappe.tests.test_query_builder import db_type_is, run_only_if
from frappe.utils.backups import backup_sqlite_database, fetch_latest_backups, new_backup


class TestSQLiteBackup(unittest.TestCase):
	def test_backup_includes_committed_wal_changes(self):
		with TemporaryDirectory() as directory:
			directory = Path(directory)
			database_path = directory / "live.db"
			backup_path = directory / "backup.db.gz"
			restored_path = directory / "restored.db"

			with sqlite3.connect(database_path) as database:
				database.execute("PRAGMA journal_mode=WAL")
				database.execute("PRAGMA wal_autocheckpoint=0")
				database.execute("CREATE TABLE test_value (value INTEGER)")
				database.execute("INSERT INTO test_value VALUES (1)")
				database.commit()
				database.execute("PRAGMA wal_checkpoint(TRUNCATE)")
				database.execute("UPDATE test_value SET value = 2")
				database.commit()

				backup_sqlite_database(database_path, backup_path)

			with gzip.open(backup_path, "rb") as backup, open(restored_path, "wb") as restored:
				restored.write(backup.read())

			with sqlite3.connect(restored_path) as restored:
				self.assertEqual(restored.execute("SELECT value FROM test_value").fetchone(), (2,))
				self.assertEqual(restored.execute("PRAGMA integrity_check").fetchone(), ("ok",))


@run_only_if(db_type_is.SQLITE)
class TestMariaDBCompatibleBackup(IntegrationTestCase):
	def write_dump(self, rows_by_table: dict[str, tuple[str, list[tuple]]]) -> str:
		with TemporaryDirectory() as directory:
			database_path = Path(directory) / "site.db"
			with contextlib.closing(sqlite3.connect(database_path)) as database:
				for table, (columns, rows) in rows_by_table.items():
					database.execute(f'CREATE TABLE "{table}" ({columns})')
					placeholders = ", ".join("?" * len(rows[0]))
					database.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
				database.commit()
			dump_path = Path(directory) / "dump.sql.gz"
			MariaDBDumpWriter(database_path).write(dump_path, "-- begin frappe metadata\n")
			with gzip.open(dump_path, "rt") as dump:
				return dump.read()

	def test_export_keeps_explicit_filters_and_stays_out_of_native_lookup(self):
		backup = new_backup(ignore_files=True, ignore_conf=True, include_doctypes="ToDo", for_mariadb=True)
		self.addCleanup(os.remove, backup.backup_path_conf)
		self.addCleanup(os.remove, backup.backup_path_db)

		self.assertTrue(backup.backup_path_db.endswith("-partial-database-mariadb.sql.gz"))
		self.assertNotEqual(fetch_latest_backups()["database"], backup.backup_path_db)
		with gzip.open(backup.backup_path_db, "rt") as dump:
			content = dump.read()
		self.assertIn("-- Partial Backup of Frappe Site", content)
		tables = set(re.findall(r"^create table `([^`]+)`", content, re.M | re.I))
		self.assertEqual(tables, {"tabToDo"})

	def test_dump_uses_mariadb_schema_and_literals(self):
		dump = self.write_dump(
			{
				"tabToDo": (
					"name varchar(140) primary key, idx int, description text, date date",
					[("todo-1", "", "it's a\nline \\ here", "2026-01-01 10:30:00")],
				),
				"table_without_doctype": ("path text default 'c:\\'", [("d:",)]),
			}
		)

		create = dump[dump.index("create table `tabToDo`") :]
		self.assertIn("name varchar(140) primary key", create)
		self.assertIn("`description` longtext", create)
		self.assertIn("COLLATE=utf8mb4_unicode_ci", create)
		self.assertIn("INSERT INTO `tabToDo` (`name`, `idx`, `description`, `date`) VALUES", dump)
		self.assertIn("('todo-1',0,'it\\'s a\\nline \\\\ here','2026-01-01')", dump)
		self.assertNotIn('"tabToDo"', dump)
		self.assertIn("SET SESSION sql_mode='STRICT_TRANS_TABLES,", dump)
		self.assertNotIn("NO_BACKSLASH_ESCAPES", dump)
		self.assertIn("`path` longtext DEFAULT 'c:\\\\'", dump)

	def test_keeps_unique_index_on_columns_with_a_plain_index(self):
		dump = self.write_dump(
			{
				"tabToDo": (
					"name varchar(140) primary key, creation datetime(6) unique",
					[("todo-1", "2026-01-01 10:30:00")],
				)
			}
		)
		self.assertIn("index creation(creation)", dump)
		self.assertRegex(dump, r"CREATE UNIQUE INDEX IF NOT EXISTS `[^`]+` ON `tabToDo` \(`creation`\);")

	def test_refuses_keys_that_collide_in_mariadb_collation(self):
		with self.assertRaises(MariaDBDumpError) as error:
			self.write_dump(
				{
					"tabRole": (
						"name varchar(140) primary key, role_name varchar(140)",
						[
							("Gate Role", "Gate Role"),
							("gate role", "gate role"),
							("Résumé", "Résumé"),
							("resume", "resume"),
						],
					)
				}
			)
		self.assertIn("tabRole", str(error.exception))
		self.assertIn("'gate role'", str(error.exception))
		self.assertIn("'resume'", str(error.exception))

	def test_refuses_numbers_mariadb_cannot_store(self):
		with self.assertRaises(MariaDBDumpError) as error:
			self.write_dump(
				{
					"tabToDo": (
						"name varchar(140) primary key, idx int",
						[("todo-1", "NaN"), ("todo-2", 2147483648), ("todo-3", 2147483647)],
					),
					"table_without_doctype": ("amount real", [(1e13,), (999999999999.5,)]),
				}
			)
		self.assertIn("tabToDo.idx: 'NaN' is not a number", str(error.exception))
		self.assertIn(
			"tabToDo.idx: 2147483648 is outside the range of int(11) (row todo-2)", str(error.exception)
		)
		self.assertIn(
			"table_without_doctype.amount: 10000000000000.0 is outside the range of decimal(21,9)",
			str(error.exception),
		)
		self.assertNotIn("2147483647", str(error.exception))
		self.assertNotIn("999999999999.5", str(error.exception))

		currency = Column("price", "decimal(3,2) NOT NULL DEFAULT 0")
		self.assertTrue(currency.is_in_range(9.99))
		self.assertTrue(currency.is_in_range(9.994))
		self.assertFalse(currency.is_in_range(9.995))
		self.assertTrue(Column("qty", "int(11)").is_in_range(2147483647.4))

	def test_refuses_text_and_json_mariadb_cannot_store(self):
		with self.assertRaises(MariaDBDumpError) as error:
			self.write_dump(
				{
					"tabComment": (
						"name varchar(140) primary key, subject text",
						[("ascii", "a" * 65536), ("emoji", "😀" * 16384), ("fits", "😀" * 16383)],
					),
					"tabBackground Task": (
						"name varchar(140) primary key, arguments text",
						[("valid", '{"a": 1}'), ("empty", ""), ("nan", '{"a": NaN}'), ("null", None)],
					),
				}
			)
		self.assertIn(
			"tabComment.subject: value of 65536 bytes exceeds text (row ascii)", str(error.exception)
		)
		self.assertIn(
			"tabComment.subject: value of 65536 bytes exceeds text (row emoji)", str(error.exception)
		)
		self.assertIn("tabBackground Task.arguments: '' is not valid JSON (row empty)", str(error.exception))
		self.assertIn(
			"""tabBackground Task.arguments: '{"a": NaN}' is not valid JSON (row nan)""", str(error.exception)
		)
		self.assertNotIn("(row fits)", str(error.exception))
		self.assertNotIn("(row valid)", str(error.exception))
		self.assertNotIn("(row null)", str(error.exception))

	def test_sequence_continues_after_the_highest_name(self):
		dump = self.write_dump(
			{
				"tabWeb Form List Column": ("name bigint primary key", [(3,), (7,)]),
				"__frappe_sqlite_sequences": (
					"name text primary key, current int, increment int, min_value int, max_value int, cycle int, declared int",
					[("web_form_list_column_id_seq", 3, 1, 1, None, 0, 1)],
				),
			}
		)
		self.assertIn("SELECT SETVAL(`web_form_list_column_id_seq`, 7, 1);", dump)

	def test_parses_keys_from_create_table(self):
		shape = parse_table_shape(
			"CREATE TABLE `t` (`a` varchar(10) NOT NULL DEFAULT 'x,y', `c` varchar(10) DEFAULT 'c:\\\\', "
			"b int UNIQUE, PRIMARY KEY (`a`), KEY `ab` (`a`, b), UNIQUE `bu` (b(10))) ENGINE=InnoDB"
		)
		self.assertEqual(shape.primary_key, ("a",))
		self.assertEqual(shape.columns["a"].default, "'x,y'")
		self.assertEqual(shape.columns["c"].default, "'c:\\\\'")
		self.assertFalse(shape.columns["a"].is_nullable)
		self.assertEqual(
			[(i.name, i.columns, i.unique) for i in shape.indexes],
			[("b", ("b",), True), ("ab", ("a", "b"), False), ("bu", ("b",), True)],
		)
