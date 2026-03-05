# Copyright (c) 2024, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.permissions import get_all_perms
from frappe.tests import IntegrationTestCase


class TestRoleReplication(IntegrationTestCase):
	def setUp(self):
		# Create a test role with permissions
		self.test_role_name = "_Test Role For Replication"
		self.new_role_name = "_Test Replicated Role"

		# Clean up any existing test roles and permissions
		self._cleanup_test_data()

		# Create the test role
		self.test_role = frappe.get_doc({"doctype": "Role", "role_name": self.test_role_name}).insert()

		# Add a DocPerm permission (simulating standard permission)
		# We use a doctype that doesn't have Custom DocPerm to simulate the bug scenario
		self.test_doctype = "User"

		# First ensure no Custom DocPerm exists for this doctype
		frappe.db.delete("Custom DocPerm", {"parent": self.test_doctype})

		# Add DocPerm for the test role
		self.test_perm = frappe.get_doc(
			{
				"doctype": "DocPerm",
				"parent": self.test_doctype,
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": self.test_role_name,
				"permlevel": 0,
				"read": 1,
				"write": 1,
				"create": 0,
			}
		).insert()

	def _cleanup_test_data(self):
		"""Clean up test roles and permissions."""
		for role_name in [self.test_role_name, self.new_role_name]:
			frappe.db.delete("Custom DocPerm", {"role": role_name})
			frappe.db.delete("DocPerm", {"role": role_name})
			if frappe.db.exists("Role", role_name):
				frappe.delete_doc("Role", role_name, force=True)

	def tearDown(self):
		self._cleanup_test_data()

	def test_replicate_role_preserves_original_permissions(self):
		"""
		Test that replicating a role does not erase the original role's permissions.
		This is a regression test for https://github.com/frappe/frappe/issues/34605
		"""
		# Get original permissions count before replication using get_all_perms
		# (this is what the Role Permissions Manager UI uses)
		original_perms_before = get_all_perms(self.test_role_name)
		self.assertTrue(
			len(original_perms_before) > 0, "Test role should have permissions before replication"
		)

		# Perform role replication
		role_replication = frappe.get_doc(
			{
				"doctype": "Role Replication",
				"existing_role": self.test_role_name,
				"new_role": self.new_role_name,
			}
		)
		role_replication.replicate_role()

		# Verify new role was created
		self.assertTrue(frappe.db.exists("Role", self.new_role_name), "New role should be created")

		# Verify new role has permissions
		new_role_perms = get_all_perms(self.new_role_name)
		self.assertTrue(len(new_role_perms) > 0, "New role should have permissions after replication")

		# Verify original role still has its permissions visible via get_all_perms
		original_perms_after = get_all_perms(self.test_role_name)
		self.assertEqual(
			len(original_perms_before),
			len(original_perms_after),
			"Original role should retain all its permissions after replication",
		)

		# Verify the original role now has Custom DocPerm entries
		original_custom_perms = frappe.get_all(
			"Custom DocPerm", filters={"role": self.test_role_name}, fields=["parent", "read", "write"]
		)
		self.assertTrue(
			len(original_custom_perms) > 0,
			"Original role should have Custom DocPerm entries after replication to preserve visibility",
		)
