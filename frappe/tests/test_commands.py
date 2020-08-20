# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors

# imports - standard imports
import shlex
import subprocess
import unittest

# imports - module imports
import frappe


def clean(value):
	if isinstance(value, (bytes, str)):
		value = value.decode().strip()
	return value


class BaseTestCommands:
	def execute(self, command):
		command = command.format(**{"site": frappe.local.site})
		command = shlex.split(command)
		self._proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		self.stdout = clean(self._proc.stdout)
		self.stderr = clean(self._proc.stderr)
		self.returncode = clean(self._proc.returncode)


class TestCommands(BaseTestCommands, unittest.TestCase):
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
