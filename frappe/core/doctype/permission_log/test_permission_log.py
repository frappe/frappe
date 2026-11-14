# Copyright (c) 2022, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.core.doctype.permission_log.permission_log import get_timeline_content, insert_perm_log
from frappe.tests import IntegrationTestCase


class TestPermissionLog(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.manager = "perm-log-manager@example.com"
		if not frappe.db.exists("User", cls.manager):
			frappe.get_doc(doctype="User", email=cls.manager, first_name="Perm Log Manager").insert()
		frappe.get_doc("User", cls.manager).add_roles("System Manager")

	def test_user_timeline_shows_role_changes(self):
		user = frappe.get_doc(doctype="User", email="perm-log@example.com", first_name="Perm Log").insert()
		user.add_roles("Website Manager")
		user.remove_roles("Website Manager")

		content = self.get_timeline_text(user.name)
		self.assertIn("added <b>Website Manager</b> to Roles Assigned", content)
		self.assertIn("removed <b>Website Manager</b> from Roles Assigned", content)

		with self.set_user(user.name):
			self.assertEqual(get_timeline_content("User", user.name), [])

	def test_user_timeline_skips_fields_shown_by_version(self):
		module_profile = frappe.get_doc(
			doctype="Module Profile", module_profile_name="Perm Log Profile"
		).insert()
		user = frappe.get_doc(doctype="User", email="perm-log-mp@example.com", first_name="Perm Log").insert()
		user.module_profile = module_profile.name
		user.save()

		content = self.get_timeline_text(user.name)
		self.assertNotIn("Module Profile", content)

	def test_user_timeline_skips_role_profile_changes(self):
		for name in ("Perm Log RP A", "Perm Log RP B"):
			frappe.get_doc(doctype="Role Profile", role_profile=name).insert()
		user = frappe.get_doc(doctype="User", email="perm-log-rp@example.com", first_name="Perm Log").insert()
		user.append("role_profiles", {"role_profile": "Perm Log RP A"})
		user.append("role_profiles", {"role_profile": "Perm Log RP B"})
		user.save()
		user.role_profiles = [row for row in user.role_profiles if row.role_profile == "Perm Log RP B"]
		user.save()
		insert_perm_log(
			user,
			custom_changes={"from": {"role_profile_name": ""}, "to": {"role_profile_name": "Perm Log RP A"}},
		)

		content = self.get_timeline_text(user.name)
		self.assertNotIn("Role Profile", content)

	def get_timeline_text(self, user: str) -> str:
		with self.set_user(self.manager):
			return " ".join(item["content"] for item in get_timeline_content("User", user))
