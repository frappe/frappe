# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors

# imports - standard imports
import os
import shlex
import subprocess
import unittest

# imports - module imports
import frappe
from frappe.utils.backups import fetch_latest_backups


def clean(value):
	if isinstance(value, (bytes, str)):
		value = value.decode().strip()
	return value


class BaseTestCommands(unittest.TestCase):
	def execute(self, command, kwargs):
		site = {"site": frappe.local.site}
		if kwargs:
			kwargs.update(site)
		else:
			kwargs = site
		command = command.replace("\n", " ").format(**kwargs)
		command = shlex.split(command)
		self._proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		self.stdout = clean(self._proc.stdout)
		self.stderr = clean(self._proc.stderr)
		self.returncode = clean(self._proc.returncode)


class TestCommands(BaseTestCommands):
	def test_execute(self):
		# test 1: execute a command expecting a numeric output
		self.execute("bench --site {site} execute frappe.db.get_database_size")
		self.assertEquals(self.returncode, 0)
		self.assertIsInstance(float(self.stdout), float)

		# test 2: execute a command expecting an errored output as local won't exist
		self.execute("bench --site {site} execute frappe.local.site")
		self.assertEquals(self.returncode, 1)
		self.assertIsNotNone(self.stderr)

		# test 3: execute a command with kwargs
		# Note:
		# terminal command has been escaped to avoid .format string replacement
		# The returned value has quotes which have been trimmed for the test
		self.execute("""bench --site {site} execute frappe.bold --kwargs '{{"text": "DocType"}}'""")
		self.assertEquals(self.returncode, 0)
		self.assertEquals(self.stdout[1:-1], frappe.bold(text='DocType'))

	def test_backup(self):
		home = os.expanduser("~")

		# test 1: take a backup
		before_backup = fetch_latest_backups()
		self.execute("bench --site {site} backup")
		after_backup = fetch_latest_backups()

		self.assertEquals(self.returncode, 0)
		self.assertIn("successfully completed", self.stdout)
		self.assertNotEqual(before_backup["database"], after_backup["database"])

		# test 2: take a backup with --with-files
		before_backup = after_backup.copy()
		self.execute("bench --site {site} backup --with-files")
		after_backup = fetch_latest_backups()

		self.assertEquals(self.returncode, 0)
		self.assertIn("successfully completed", self.stdout)
		self.assertIn("with files", self.stdout)
		self.assertNotEqual(before_backup, after_backup)
		self.assertIsNotNone(after_backup["public"])
		self.assertIsNotNone(after_backup["private"])

		# test 3: take a backup with --backup-path
		backup_path = os.path.join(home, "backups")
		self.execute("bench --site {site} backup --backup-path {backup_path}", {"backup_path": backup_path})

		self.assertEquals(self.returncode, 0)
		self.assertTrue(os.path.exists(backup_path))
		self.assertGreaterEqual(len(os.listdir(backup_path)), 2)

		# test 4: take a backup with --backup-path-db, --backup-path-files, --backup-path-private-files, --backup-path-conf
		kwargs = { key: os.path.join(home, key) for key in ["db_path", "files_path", "private_path", "conf_path"] }

		self.execute("""bench
			--site {site} backup --with-files
			--backup-path-db {db_path}
			--backup-path-files {files_path}
			--backup-path-private-files {private_path}
			--backup-path-conf {conf_path}""", kwargs)

		self.assertEquals(self.returncode, 0)
		for path in kwargs.values():
			self.assertTrue(len(os.listdir(path)), 1)

		# test 5: take a backup with --compress
		self.execute("bench --site {site} backup --with-files --compress")
		backup_files = fetch_latest_backups()

		self.assertEquals(self.returncode, 0)
		self.assertTrue(backup_files["private"].endswith("tgz"))
		self.assertTrue(backup_files["public"].endswith("tgz"))

		# test 6: take a backup with --verbose
		self.execute("bench --site {site} backup --verbose")
		self.assertEquals(self.returncode, 0)
