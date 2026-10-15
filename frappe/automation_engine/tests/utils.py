# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase


class AutomationEngineTestCase(IntegrationTestCase):
	def make_todo(self, **kwargs):
		return frappe.get_doc({"doctype": "ToDo", "description": "x", **kwargs}).insert()

	def assert_no_queries(self, fn):
		with self.assertQueryCount(0):
			return fn()
