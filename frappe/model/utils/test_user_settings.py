# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.utils.user_settings import get, save
from frappe.tests import IntegrationTestCase


class TestUserSettings(IntegrationTestCase):
	def test_save_accepts_native_dict(self):
		# user_settings as a native dict instead of a JSON string (frappe.parse_json passthrough)
		saved = save("ToDo", {"sort_by": "modified"})
		self.assertEqual(saved["sort_by"], "modified")

		stored = frappe.parse_json(get("ToDo"))
		self.assertEqual(stored.get("sort_by"), "modified")
