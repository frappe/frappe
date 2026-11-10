import gzip
import os
import sqlite3
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from frappe.tests import IntegrationTestCase
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
