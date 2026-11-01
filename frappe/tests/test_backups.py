import gzip
import os
import sqlite3
import tarfile
import time
import unittest
from glob import glob
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.backups import (
	backup_sqlite_database,
	fetch_latest_backups,
	get_backup_path,
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

	def test_backup_includes_server_scripts_archive(self):
		with TemporaryDirectory() as directory:
			odb = scheduled_backup(ignore_files=True, force=True, backup_path=directory)

			path = odb.backup_path_server_scripts
			self.assertIn("-server-scripts.tar", path)
			self.assertTrue(os.path.exists(path))
			self.assertTrue(any(name.endswith(self.SCRIPT) for name in self.archive_names(path)))
			self.assertEqual(odb.get_summary()["server_scripts"]["path"], path)

	def test_backup_without_scripts_folder_makes_no_archive(self):
		real_get_site_path = frappe.get_site_path

		def get_site_path(*parts):
			if parts == ("server_scripts",):
				return os.path.join(directory, "missing")
			return real_get_site_path(*parts)

		with TemporaryDirectory() as directory:
			with patch("frappe.get_site_path", get_site_path):
				odb = scheduled_backup(ignore_files=True, force=True, backup_path=directory)

			self.assertFalse(os.path.exists(odb.backup_path_server_scripts))
			self.assertNotIn("server_scripts", odb.get_summary())

	def test_caller_managed_database_backup_leaves_no_archive(self):
		before = set(glob(os.path.join(get_backup_path(), "*-server-scripts*")))
		with TemporaryDirectory() as directory:
			scheduled_backup(
				ignore_files=True,
				force=True,
				backup_path_db=os.path.join(directory, "db.sql.gz"),
				backup_path_conf=os.path.join(directory, "conf.json"),
			)
		after = set(glob(os.path.join(get_backup_path(), "*-server-scripts*")))
		self.assertEqual(after, before)

	def test_compressed_backup_archive(self):
		with TemporaryDirectory() as directory:
			odb = scheduled_backup(ignore_files=True, force=True, backup_path=directory, compress=True)

			path = odb.backup_path_server_scripts
			self.assertTrue(path.endswith(".tgz"))
			with tarfile.open(path, "r:gz") as archive:
				self.assertTrue(any(name.endswith(self.SCRIPT) for name in archive.getnames()))

	@unittest.skipUnless(which("gpg"), "gpg is required for encrypted backups")
	def test_encrypted_backup_archive_is_not_plain_tar(self):
		settings = frappe.get_single("System Settings")
		original = settings.encrypt_backup
		settings.encrypt_backup = 1
		settings.save()
		self.addCleanup(lambda: frappe.db.set_single_value("System Settings", "encrypt_backup", original))

		with TemporaryDirectory() as directory:
			odb = scheduled_backup(ignore_files=True, force=True, backup_path=directory)

			path = odb.backup_path_server_scripts
			self.assertIn("-server-scripts-enc.tar", path)
			self.assertTrue(os.path.exists(path))
			self.assertFalse(tarfile.is_tarfile(path))
