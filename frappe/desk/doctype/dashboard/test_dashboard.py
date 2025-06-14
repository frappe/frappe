# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.user.test_user import test_user
from frappe.tests import IntegrationTestCase
from frappe.utils.modules import get_modules_from_all_apps_for_user


class TestDashboard(IntegrationTestCase):
	def test_permission_query(self):
		for user in ["Administrator", "test@example.com"]:
			with self.set_user(user):
				frappe.get_list("Dashboard")

		with test_user(roles=["_Test Role"]) as user:
			with self.set_user(user.name):
				frappe.get_list("Dashboard")
				with self.set_user("Administrator"):
					all_modules = get_modules_from_all_apps_for_user("Administrator")
					for module in all_modules:
						user.append("block_modules", {"module": module.get("module_name")})
					user.save()
				frappe.get_list("Dashboard")
