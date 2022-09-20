# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests.utils import FrappeTestCase


class TestSystemConsole(FrappeTestCase):
	def test_system_console(self):
		system_console = frappe.get_doc("System Console")
		system_console.console = 'log("hello")'
		system_console.run()

		self.assertEqual(system_console.output, "hello")

		system_console.console = 'log(frappe.db.get_value("DocType", "DocType", "module"))'
		system_console.run()

		self.assertEqual(system_console.output, "Core")
