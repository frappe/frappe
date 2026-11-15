import gzip
import os
import sqlite3
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from frappe.database.sqlite.mariadb_dump import MariaDBDumpError, MariaDBDumpWriter, parse_table_shape
from frappe.tests import IntegrationTestCase
from frappe.tests.test_query_builder import db_type_is, run_only_if
from frappe.utils.backups import backup_sqlite_database, fetch_latest_backups


class TestLatestBackup(IntegrationTestCase):
	def test_same_second_backups_resolve_to_the_newer_file(self):
		with TemporaryDirectory() as directory:
			full = Path(directory) / "20990101_000000-site-database.sql.gz"
			partial = Path(directory) / "20990101_000000-site-partial-database.sql.gz"
			full.touch()
			partial.touch()
			os.utime(full, (time.time() - 1, time.time() - 1))

			# list the older file first so glob order alone would pick it
			with patch("frappe.utils.backups.glob", return_value=[str(full), str(partial)]):
				self.assertEqual(fetch_latest_backups(partial=True)["database"], str(partial))


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
			with sqlite3.connect(database_path) as database:
				for table, (columns, rows) in rows_by_table.items():
					database.execute(f'CREATE TABLE "{table}" ({columns})')
					placeholders = ", ".join("?" * len(rows[0]))
					database.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
			dump_path = Path(directory) / "dump.sql.gz"
			MariaDBDumpWriter(database_path).write(dump_path, "-- begin frappe metadata\n")
			with gzip.open(dump_path, "rt") as dump:
				return dump.read()

	def test_dump_uses_mariadb_schema_and_literals(self):
		dump = self.write_dump(
			{
				"tabToDo": (
					"name varchar(140) primary key, idx int, description text, date date",
					[("todo-1", "", "it's a\nline \\ here", "2026-01-01 10:30:00")],
				)
			}
		)

		create = dump[dump.index("create table `tabToDo`") :]
		self.assertIn("name varchar(140) primary key", create)
		self.assertIn("`description` longtext", create)
		self.assertIn("COLLATE=utf8mb4_unicode_ci", create)
		self.assertIn("INSERT INTO `tabToDo` (`name`, `idx`, `description`, `date`) VALUES", dump)
		self.assertIn("('todo-1',0,'it\\'s a\\nline \\\\ here','2026-01-01')", dump)
		self.assertNotIn('"tabToDo"', dump)

	def test_refuses_keys_that_collide_in_mariadb_collation(self):
		with self.assertRaises(MariaDBDumpError) as error:
			self.write_dump(
				{
					"tabRole": (
						"name varchar(140) primary key, role_name varchar(140)",
						[("Gate Role", "Gate Role"), ("gate role", "gate role")],
					)
				}
			)
		self.assertIn("tabRole", str(error.exception))
		self.assertIn("'gate role'", str(error.exception))

	def test_refuses_non_finite_numbers(self):
		with self.assertRaises(MariaDBDumpError) as error:
			self.write_dump({"tabToDo": ("name varchar(140) primary key, idx int", [("todo-1", "NaN")])})
		self.assertIn("tabToDo.idx: 'NaN' is not a number", str(error.exception))

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
			"CREATE TABLE `t` (`a` varchar(10) NOT NULL DEFAULT 'x,y', b int UNIQUE, "
			"PRIMARY KEY (`a`), KEY `ab` (`a`, b), UNIQUE `bu` (b(10))) ENGINE=InnoDB"
		)
		self.assertEqual(shape.primary_key, ("a",))
		self.assertEqual(shape.columns["a"].default, "'x,y'")
		self.assertFalse(shape.columns["a"].is_nullable)
		self.assertEqual(
			[(i.name, i.columns, i.unique) for i in shape.indexes],
			[("b", ("b",), True), ("ab", ("a", "b"), False), ("bu", ("b",), True)],
		)
