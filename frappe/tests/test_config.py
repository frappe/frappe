# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.modules import get_modules_from_all_apps_for_user


class TestConfig(IntegrationTestCase):
	def test_get_modules(self):
		frappe_modules = frappe.get_all("Module Def", filters={"app_name": "frappe"}, pluck="name")
		all_modules_data = get_modules_from_all_apps_for_user()
		all_modules = [x["module_name"] for x in all_modules_data]
		self.assertIsInstance(all_modules_data, list)
		self.assertFalse([x for x in frappe_modules if x not in all_modules])
