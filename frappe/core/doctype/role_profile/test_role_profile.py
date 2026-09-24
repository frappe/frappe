# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = ["Role"]


class TestRoleProfile(IntegrationTestCase):
	def test_make_new_role_profiles(self):
		frappe.delete_doc_if_exists("Role Profile", "Test 1", force=1)
		new_role_profile = frappe.get_doc(doctype="Role Profile", role_profile="Test 1").insert()

		self.assertEqual(new_role_profile.role_profile, "Test 1")

		# add role
		new_role_profile.append("roles", {"role": "_Test Role 2"})
		new_role_profile.save()
		self.assertEqual(new_role_profile.roles[0].role, "_Test Role 2")

		# user with a role profile
		random_user = frappe.mock("email")
		random_user_name = frappe.mock("name")

		user_role_profile = [{"role_profile": "Test 1"}]

		random_user = frappe.get_doc(
			{
				"doctype": "User",
				"email": random_user,
				"enabled": 1,
				"first_name": random_user_name,
				"new_password": "Eastern_43A1W",
				"role_profiles": user_role_profile,
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)

		self.assertEqual(
			{role.role for role in random_user.roles}, {role.role for role in new_role_profile.roles}
		)

		# clear roles
		new_role_profile.roles = []
		new_role_profile.save()
		self.assertEqual(new_role_profile.roles, [])

		# user roles with the role profile should also be updated
		random_user.reload()
		self.assertListEqual(random_user.roles, [])

	def test_multiple_role_profiles(self):
		frappe.delete_doc_if_exists("Role Profile", "_Test Role Profile 1", force=1)
		frappe.delete_doc_if_exists("Role Profile", "_Test Role Profile 2", force=1)

		role_profile_one = frappe.get_doc(doctype="Role Profile", role_profile="_Test Role Profile 1").insert(
			ignore_if_duplicate=True
		)
		role_profile_two = frappe.get_doc(doctype="Role Profile", role_profile="_Test Role Profile 2").insert(
			ignore_if_duplicate=True
		)

		self.assertEqual(role_profile_one.role_profile, "_Test Role Profile 1")
		self.assertEqual(role_profile_two.role_profile, "_Test Role Profile 2")

		# Create new role for test
		frappe.get_doc(doctype="Role", role_name="_Test Role 1").insert(ignore_if_duplicate=True)
		frappe.get_doc(doctype="Role", role_name="_Test Role 2").insert(ignore_if_duplicate=True)
		frappe.get_doc(doctype="Role", role_name="_Test Role 3").insert(ignore_if_duplicate=True)
		# add role
		role_profile_one.update({"roles": [{"role": "_Test Role 1"}, {"role": "_Test Role 2"}]})
		role_profile_one.save()

		role_profile_two.update({"roles": [{"role": "_Test Role 2"}, {"role": "_Test Role 3"}]})
		role_profile_two.save()

		self.assertEqual(role_profile_one.roles[0].role, "_Test Role 1")
		self.assertEqual(role_profile_two.roles[1].role, "_Test Role 3")

		# create user with a role profile

		user_one = frappe.get_doc(
			{
				"doctype": "User",
				"email": frappe.mock("email"),
				"enabled": 1,
				"first_name": frappe.mock("name"),
				"new_password": "Eastern_43A1W",
				"role_profiles": [
					{"role_profile": "_Test Role Profile 1"},
					{"role_profile": "_Test Role Profile 2"},
				],
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)

		user_two = frappe.get_doc(
			{
				"doctype": "User",
				"email": frappe.mock("email"),
				"enabled": 1,
				"first_name": frappe.mock("name"),
				"new_password": "Eastern_43A1W",
				"role_profiles": [{"role_profile": "_Test Role Profile 2"}],
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)

		for role in role_profile_one.roles:
			self.assertIn(role.role, [role.role for role in user_one.roles])

		self.assertEqual(
			{role.role for role in user_two.roles}, {role.role for role in role_profile_two.roles}
		)

	def create_role_profile(self, name, role):
		frappe.delete_doc_if_exists("Role Profile", name, force=1)

		return frappe.get_doc(doctype="Role Profile", role_profile=name, roles=[{"role": role}]).insert()

	def create_user(self, **kwargs):
		return frappe.get_doc(
			doctype="User", email=frappe.mock("email"), first_name=frappe.mock("name"), **kwargs
		).insert(ignore_permissions=True)

	def test_deprecated_role_profile_name_is_moved_to_role_profiles(self):
		self.create_role_profile("_Test Role Profile 1", "_Test Role 2")

		user = self.create_user(role_profile_name="_Test Role Profile 1")

		self.assertEqual([r.role_profile for r in user.role_profiles], ["_Test Role Profile 1"])
		self.assertIn("_Test Role 2", [r.role for r in user.roles])

	def test_removing_role_profiles(self):
		self.create_role_profile("_Test Role Profile 1", "_Test Role 2")
		self.create_role_profile("_Test Role Profile 2", "_Test Role 3")

		user = self.create_user(
			role_profiles=[{"role_profile": "_Test Role Profile 1"}, {"role_profile": "_Test Role Profile 2"}]
		)
		user.reload()

		user.role_profiles = [r for r in user.role_profiles if r.role_profile != "_Test Role Profile 1"]
		user.save()
		user.reload()
		self.assertEqual([r.role_profile for r in user.role_profiles], ["_Test Role Profile 2"])

		user.role_profiles = []
		user.save()
		user.reload()
		self.assertEqual(user.role_profiles, [])

	def test_update_role_profile(self):
		role_profile = frappe.get_doc("Role Profile", "_Test Role Profile 1")

		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": frappe.mock("email"),
				"enabled": 1,
				"first_name": frappe.mock("name"),
				"new_password": "Eastern_43A1W",
				"role_profiles": [{"role_profile": "_Test Role Profile 1"}],
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)

		role_profile.update(
			{"roles": [{"role": "_Test Role 1"}, {"role": "_Test Role 3"}, {"role": "_Test Role 2"}]}
		)
		role_profile.save()

		user.reload()
		self.assertEqual({role.role for role in user.roles}, {role.role for role in role_profile.roles})
