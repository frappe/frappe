# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors

# imports - standard imports
import gzip
import json
import os
import shlex
import subprocess
import sys
import unittest
import glob

# imports - module imports
import frappe
import frappe.recorder
from frappe.installer import add_to_installed_apps
from frappe.utils import add_to_date, get_bench_relative_path, now
from frappe.utils.backups import fetch_latest_backups


# TODO: check frappe.cli.coloured_output to set coloured output!
def supports_color():
	"""
	Returns True if the running system's terminal supports color, and False
	otherwise.
	"""
	plat = sys.platform
	supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
	# isatty is not always implemented, #6223.
	is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
	return supported_platform and is_a_tty


class color(dict):
	nc = "\033[0m"
	blue = "\033[94m"
	green = "\033[92m"
	yellow = "\033[93m"
	red = "\033[91m"
	silver = "\033[90m"

	def __getattr__(self, key):
		if supports_color():
			ret = self.get(key)
		else:
			ret = ""
		return ret


def clean(value):
	"""Strips and converts bytes to str

	Args:
		value ([type]): [description]

	Returns:
		[type]: [description]
	"""
	if isinstance(value, bytes):
		value = value.decode()
	if isinstance(value, str):
		value = value.strip()
	return value


def exists_in_backup(doctypes, file):
	"""Checks if the list of doctypes exist in the database.sql.gz file supplied

	Args:
		doctypes (list): List of DocTypes to be checked
		file (str): Path of the database file

	Returns:
		bool: True if all tables exist
	"""
	predicate = (
		'COPY public."tab{}"'
		if frappe.conf.db_type == "postgres"
		else "CREATE TABLE `tab{}`"
	)
	with gzip.open(file, "rb") as f:
		content = f.read().decode("utf8")
	return all([predicate.format(doctype).lower() in content.lower() for doctype in doctypes])


class BaseTestCommands(unittest.TestCase):
	def execute(self, command, kwargs=None):
		site = {"site": frappe.local.site}
		if kwargs:
			kwargs.update(site)
		else:
			kwargs = site
		self.command = " ".join(command.split()).format(**kwargs)
		print("{0}$ {1}{2}".format(color.silver, self.command, color.nc))
		command = shlex.split(self.command)
		self._proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		self.stdout = clean(self._proc.stdout)
		self.stderr = clean(self._proc.stderr)
		self.returncode = clean(self._proc.returncode)

	def _formatMessage(self, msg, standardMsg):
		output = super(BaseTestCommands, self)._formatMessage(msg, standardMsg)
		cmd_execution_summary = "\n".join([
			"-" * 70,
			"Last Command Execution Summary:",
			"Command: {}".format(self.command) if self.command else "",
			"Standard Output: {}".format(self.stdout) if self.stdout else "",
			"Standard Error: {}".format(self.stderr) if self.stderr else "",
			"Return Code: {}".format(self.returncode) if self.returncode else "",
		]).strip()
		return "{}\n\n{}".format(output, cmd_execution_summary)


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
		self.assertEquals(self.stdout[1:-1], frappe.bold(text="DocType"))

	def test_backup(self):
		backup = {
			"includes": {
				"includes": [
					"ToDo",
					"Note",
				]
			},
			"excludes": {
				"excludes": [
					"Activity Log",
					"Access Log",
					"Error Log"
				]
			}
		}
		home = os.path.expanduser("~")
		site_backup_path = frappe.utils.get_site_path("private", "backups")

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
		kwargs = {
			key: os.path.join(home, key, value)
			for key, value in {
				"db_path": "database.sql.gz",
				"files_path": "public.tar",
				"private_path": "private.tar",
				"conf_path": "config.json",
			}.items()
		}

		self.execute(
			"""bench
			--site {site} backup --with-files
			--backup-path-db {db_path}
			--backup-path-files {files_path}
			--backup-path-private-files {private_path}
			--backup-path-conf {conf_path}""",
			kwargs,
		)

		self.assertEquals(self.returncode, 0)
		for path in kwargs.values():
			self.assertTrue(os.path.exists(path))

		# test 5: take a backup with --compress
		self.execute("bench --site {site} backup --with-files --compress")
		self.assertEquals(self.returncode, 0)
		compressed_files = glob.glob(site_backup_path + "/*.tgz")
		self.assertGreater(len(compressed_files), 0)

		# test 6: take a backup with --verbose
		self.execute("bench --site {site} backup --verbose")
		self.assertEquals(self.returncode, 0)

		# test 7: take a backup with frappe.conf.backup.includes
		self.execute(
			"bench --site {site} set-config backup '{includes}' --parse",
			{"includes": json.dumps(backup["includes"])},
		)
		self.execute("bench --site {site} backup --verbose")
		self.assertEquals(self.returncode, 0)
		database = fetch_latest_backups(partial=True)["database"]
		self.assertTrue(exists_in_backup(backup["includes"]["includes"], database))

		# test 8: take a backup with frappe.conf.backup.excludes
		self.execute(
			"bench --site {site} set-config backup '{excludes}' --parse",
			{"excludes": json.dumps(backup["excludes"])},
		)
		self.execute("bench --site {site} backup --verbose")
		self.assertEquals(self.returncode, 0)
		database = fetch_latest_backups(partial=True)["database"]
		self.assertFalse(exists_in_backup(backup["excludes"]["excludes"], database))
		self.assertTrue(exists_in_backup(backup["includes"]["includes"], database))

		# test 9: take a backup with --include (with frappe.conf.excludes still set)
		self.execute(
			"bench --site {site} backup --include '{include}'",
			{"include": ",".join(backup["includes"]["includes"])},
		)
		self.assertEquals(self.returncode, 0)
		database = fetch_latest_backups(partial=True)["database"]
		self.assertTrue(exists_in_backup(backup["includes"]["includes"], database))

		# test 10: take a backup with --exclude
		self.execute(
			"bench --site {site} backup --exclude '{exclude}'",
			{"exclude": ",".join(backup["excludes"]["excludes"])},
		)
		self.assertEquals(self.returncode, 0)
		database = fetch_latest_backups(partial=True)["database"]
		self.assertFalse(exists_in_backup(backup["excludes"]["excludes"], database))

		# test 11: take a backup with --ignore-backup-conf
		self.execute("bench --site {site} backup --ignore-backup-conf")
		self.assertEquals(self.returncode, 0)
		database = fetch_latest_backups()["database"]
		self.assertTrue(exists_in_backup(backup["excludes"]["excludes"], database))

	def test_restore(self):
		# step 0: create a site to run the test on
		global_config = {
			"admin_password": frappe.conf.admin_password,
			"root_login": frappe.conf.root_login,
			"root_password": frappe.conf.root_password,
			"db_type": frappe.conf.db_type,
		}
		site_data = {"another_site": f"{frappe.local.site}-restore.test", **global_config}
		for key, value in global_config.items():
			if value:
				self.execute(f"bench set-config {key} {value} -g")
		self.execute(
			"bench new-site {another_site} --admin-password {admin_password} --db-type"
			" {db_type}",
			site_data,
		)

		# test 1: bench restore from full backup
		self.execute("bench --site {another_site} backup --ignore-backup-conf", site_data)
		self.execute(
			"bench --site {another_site} execute frappe.utils.backups.fetch_latest_backups",
			site_data,
		)
		site_data.update({"database": json.loads(self.stdout)["database"]})
		self.execute("bench --site {another_site} restore {database}", site_data)

		# test 2: restore from partial backup
		self.execute("bench --site {another_site} backup --exclude 'ToDo'", site_data)
		site_data.update({"kw": "\"{'partial':True}\""})
		self.execute(
			"bench --site {another_site} execute"
			" frappe.utils.backups.fetch_latest_backups --kwargs {kw}",
			site_data,
		)
		site_data.update({"database": json.loads(self.stdout)["database"]})
		self.execute("bench --site {another_site} restore {database}", site_data)
		self.assertEquals(self.returncode, 1)

	def test_partial_restore(self):
		_now = now()
		for num in range(10):
			frappe.get_doc({
				"doctype": "ToDo",
				"date": add_to_date(_now, days=num),
				"description": frappe.mock("paragraph")
			}).insert()
		frappe.db.commit()
		todo_count = frappe.db.count("ToDo")

		# check if todos exist, create a partial backup and see if the state is the same after restore
		self.assertIsNot(todo_count, 0)
		self.execute("bench --site {site} backup --only 'ToDo'")
		db_path = fetch_latest_backups(partial=True)["database"]
		self.assertTrue("partial" in db_path)

		frappe.db.sql_ddl("DROP TABLE IF EXISTS `tabToDo`")
		frappe.db.commit()

		self.execute("bench --site {site} partial-restore {path}", {"path": db_path})
		self.assertEquals(self.returncode, 0)
		self.assertEquals(frappe.db.count("ToDo"), todo_count)

	def test_recorder(self):
		frappe.recorder.stop()

		self.execute("bench --site {site} start-recording")
		frappe.local.cache = {}
		self.assertEqual(frappe.recorder.status(), True)

		self.execute("bench --site {site} stop-recording")
		frappe.local.cache = {}
		self.assertEqual(frappe.recorder.status(), False)

	def test_remove_from_installed_apps(self):
		app = "test_remove_app"
		add_to_installed_apps(app)

		# check: confirm that add_to_installed_apps added the app in the default
		self.execute("bench --site {site} list-apps")
		self.assertIn(app, self.stdout)

		# test 1: remove app from installed_apps global default
		self.execute("bench --site {site} remove-from-installed-apps {app}", {"app": app})
		self.assertEquals(self.returncode, 0)
		self.execute("bench --site {site} list-apps")
		self.assertNotIn(app, self.stdout)

	def test_list_apps(self):
		# test 1: sanity check for command
		self.execute("bench --site all list-apps")
		self.assertEquals(self.returncode, 0)

		# test 2: bare functionality for single site
		self.execute("bench --site {site} list-apps")
		self.assertEquals(self.returncode, 0)
		list_apps = set([
			_x.split()[0] for _x in self.stdout.split("\n")
		])
		doctype = frappe.get_single("Installed Applications").installed_applications
		if doctype:
			installed_apps = set([x.app_name for x in doctype])
		else:
			installed_apps = set(frappe.get_installed_apps())
		self.assertSetEqual(list_apps, installed_apps)

		# test 3: parse json format
		self.execute("bench --site all list-apps --format json")
		self.assertEquals(self.returncode, 0)
		self.assertIsInstance(json.loads(self.stdout), dict)

		self.execute("bench --site {site} list-apps --format json")
		self.assertIsInstance(json.loads(self.stdout), dict)

		self.execute("bench --site {site} list-apps -f json")
		self.assertIsInstance(json.loads(self.stdout), dict)

	def test_show_config(self):
		# test 1: sanity check for command
		self.execute("bench --site all show-config")
		self.assertEquals(self.returncode, 0)

		# test 2: test keys in table text
		self.execute(
			"bench --site {site} set-config test_key '{second_order}' --parse",
			{"second_order": json.dumps({"test_key": "test_value"})},
		)
		self.execute("bench --site {site} show-config")
		self.assertEquals(self.returncode, 0)
		self.assertIn("test_key.test_key", self.stdout.split())
		self.assertIn("test_value", self.stdout.split())

		# test 3: parse json format
		self.execute("bench --site all show-config --format json")
		self.assertEquals(self.returncode, 0)
		self.assertIsInstance(json.loads(self.stdout), dict)

		self.execute("bench --site {site} show-config --format json")
		self.assertIsInstance(json.loads(self.stdout), dict)

		self.execute("bench --site {site} show-config -f json")
		self.assertIsInstance(json.loads(self.stdout), dict)

	def test_get_bench_relative_path(self):
		bench_path = frappe.utils.get_bench_path()
		test1_path = os.path.join(bench_path, "test1.txt")
		test2_path = os.path.join(bench_path, "sites", "test2.txt")

		with open(test1_path, "w+") as test1:
			test1.write("asdf")
		with open(test2_path, "w+") as test2:
			test2.write("asdf")

		self.assertTrue("test1.txt" in get_bench_relative_path("test1.txt"))
		self.assertTrue("sites/test2.txt" in get_bench_relative_path("test2.txt"))
		with self.assertRaises(SystemExit):
			get_bench_relative_path("test3.txt")

		os.remove(test1_path)
		os.remove(test2_path)

	def test_frappe_site_env(self):
		os.putenv('FRAPPE_SITE', frappe.local.site)
		self.execute("bench execute frappe.ping")
		self.assertEquals(self.returncode, 0)
		self.assertIn("pong", self.stdout)

	def test_version(self):
		self.execute("bench version")
		self.assertEqual(self.returncode, 0)

		for output in ["legacy", "plain", "table", "json"]:
			self.execute(f"bench version -f {output}")
			self.assertEqual(self.returncode, 0)
		
		self.execute("bench version -f invalid")
		self.assertEqual(self.returncode, 2)
