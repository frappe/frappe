# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.core.report.user_doctype_permissions.user_doctype_permissions import execute
from frappe.tests import IntegrationTestCase


class TestUserDoctypePermissions(IntegrationTestCase):
	def test_custom_docperm_without_doctype(self):
		role = frappe.get_doc({"doctype": "Role", "role_name": "_Test Orphan Perm Role"}).insert()

		user = frappe.new_doc("User")
		user.email = "orphan_docperm@example.com"
		user.first_name = "Orphan"
		user.send_welcome_email = 0
		user.add_roles("System Manager", role.name)

		with self.set_user(user.name):
			_, before = execute({"user": user.name})

		self.assertTrue(before)

		# `Custom DocPerm` is not a child table, so nothing populates `parent`
		frappe.get_doc({"doctype": "Custom DocPerm", "role": role.name, "permlevel": 0, "read": 1}).insert()

		with self.set_user(user.name):
			_, after = execute({"user": user.name})

		# a permission bound to no DocType grants nothing, so it must not reach the report
		self.assertEqual(before, after)
