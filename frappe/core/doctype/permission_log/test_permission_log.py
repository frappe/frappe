# Copyright (c) 2022, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.core.doctype.permission_log.permission_log import get_timeline_content
from frappe.tests import IntegrationTestCase


class TestPermissionLog(IntegrationTestCase):
	def test_user_timeline_shows_role_changes(self):
		user = frappe.get_doc(doctype="User", email="perm-log@example.com", first_name="Perm Log").insert()
		user.add_roles("Website Manager")
		user.remove_roles("Website Manager")

		content = " ".join(item["content"] for item in get_timeline_content("User", user.name))
		self.assertIn("added <b>Website Manager</b> to Roles Assigned", content)
		self.assertIn("removed <b>Website Manager</b> from Roles Assigned", content)

		with self.set_user(user.name):
			self.assertEqual(get_timeline_content("User", user.name), [])
