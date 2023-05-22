# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests.utils import FrappeTestCase


class TestModuleProfile(FrappeTestCase):
	def test_make_new_module_profile(self):
		if not frappe.db.get_value("Module Profile", "_Test Module Profile"):
			frappe.get_doc(
				{
					"doctype": "Module Profile",
					"module_profile_name": "_Test Module Profile",
					"block_modules": [{"module": "Accounts"}],
				}
			).insert()

		# add to user and check
		if not frappe.db.get_value("User", "test-for-module_profile@example.com"):
			new_user = frappe.get_doc(
				{"doctype": "User", "email": "test-for-module_profile@example.com", "first_name": "Test User"}
			).insert()
		else:
			new_user = frappe.get_doc("User", "test-for-module_profile@example.com")

		new_user.module_profile = "_Test Module Profile"
		new_user.save()

		self.assertEqual(new_user.block_modules[0].module, "Accounts")
