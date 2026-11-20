import gzip
import os
import sqlite3
import subprocess
import tarfile
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.backups import (
	backup_sqlite_database,
	fetch_latest_backups,
	scheduled_backup,
)


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


class TestServerScriptsBackup(IntegrationTestCase):
	SCRIPT = "zz_backup_test.py"

	def setUp(self):
		self.scripts_dir = frappe.get_site_path("server_scripts")
		os.makedirs(self.scripts_dir, exist_ok=True)
		self.script_path = os.path.join(self.scripts_dir, self.SCRIPT)
		with open(self.script_path, "w") as f:
			f.write("doc.status = 'Closed'\n")
		self.addCleanup(lambda: os.path.exists(self.script_path) and os.remove(self.script_path))

	def archive_names(self, path):
		with tarfile.open(path) as archive:
			return archive.getnames()

	def has_script(self, names):
		return any(name.endswith(f"server_scripts/{self.SCRIPT}") for name in names)

	def test_private_files_backup_includes_server_scripts(self):
		with TemporaryDirectory() as directory:
			odb = scheduled_backup(ignore_files=False, force=True, backup_path=directory)

			self.assertTrue(self.has_script(self.archive_names(odb.backup_path_private_files)))
			self.assertFalse(self.has_script(self.archive_names(odb.backup_path_files)))

	def test_backup_without_scripts_folder(self):
		real_get_site_path = frappe.get_site_path

		def get_site_path(*parts):
			if parts == ("server_scripts",):
				return os.path.join(directory, "missing")
			return real_get_site_path(*parts)

		with TemporaryDirectory() as directory:
			with patch("frappe.get_site_path", get_site_path):
				odb = scheduled_backup(ignore_files=False, force=True, backup_path=directory)

			self.assertFalse(self.has_script(self.archive_names(odb.backup_path_private_files)))

	def test_compressed_private_files_backup_includes_server_scripts(self):
		with TemporaryDirectory() as directory:
			odb = scheduled_backup(ignore_files=False, force=True, backup_path=directory, compress=True)

			self.assertTrue(odb.backup_path_private_files.endswith(".tgz"))
			self.assertTrue(self.has_script(self.archive_names(odb.backup_path_private_files)))

	def test_restoring_private_files_brings_back_server_scripts(self):
		with TemporaryDirectory() as directory:
			odb = scheduled_backup(ignore_files=False, force=True, backup_path=directory)
			archive = os.path.abspath(odb.backup_path_private_files)
			os.remove(self.script_path)

			# the same extraction frappe.installer.extract_files runs on restore
			subprocess.run(["tar", "xf", archive, "--strip", "2"], cwd=frappe.get_site_path(), check=True)

			with open(self.script_path) as f:
				self.assertEqual(f.read(), "doc.status = 'Closed'\n")
