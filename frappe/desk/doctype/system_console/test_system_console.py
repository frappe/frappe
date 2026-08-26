# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.desk.doctype.system_console.system_console import execute_code
from frappe.tests import IntegrationTestCase


class TestSystemConsole(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.enterClassContext(cls.enable_safe_exec())
		return super().setUpClass()

	def test_system_console(self):
		system_console = frappe.get_doc("System Console")
		system_console.console = 'log("hello")'
		system_console.run()

		self.assertEqual(system_console.output, "hello")

		system_console.console = 'log(frappe.db.get_value("DocType", "DocType", "module"))'
		system_console.run()

		self.assertEqual(system_console.output, "Core")

	def test_system_console_sql(self):
		system_console = frappe.get_doc("System Console")
		system_console.type = "SQL"
		system_console.console = "select 'test'"
		system_console.run()

		self.assertIn("test", system_console.output)

		system_console.console = "update `tabDocType` set is_virtual = 1 where name = 'xyz'"
		system_console.run()

		self.assertIn("PermissionError", system_console.output)

	def test_execute_code_with_string(self):
		"""execute_code should work with a JSON string (old call signature)."""
		doc = frappe.as_json({"doctype": "System Console", "console": 'log("hello")', "type": "Python"})
		result = execute_code(doc)
		self.assertEqual(result.get("output"), "hello")

	def test_execute_code_with_dict(self):
		"""execute_code should work with an already-parsed dict."""
		doc = {"doctype": "System Console", "console": 'log("hello")', "type": "Python"}
		result = execute_code(doc)
		self.assertEqual(result.get("output"), "hello")
