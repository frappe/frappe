# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.desktop import get_desktop_page
from frappe.tests import IntegrationTestCase


class TestDesktop(IntegrationTestCase):
	def test_get_desktop_page_accepts_native_dict(self):
		workspace = frappe.db.get_value("Workspace", {"public": 1}, "name")
		# page as a native dict instead of a JSON string (frappe.parse_json passthrough)
		result = get_desktop_page({"name": workspace})
		self.assertIsInstance(result, dict)
		self.assertIn("charts", result)
