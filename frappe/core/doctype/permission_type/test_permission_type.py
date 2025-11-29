# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.permissions import update_permission_property
from frappe.tests import IntegrationTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestPermissionType(IntegrationTestCase):
	"""
	Integration tests for PermissionType.
	Use this class for testing interactions between multiple components.
	"""

	def test_approve_ptype_on_blog_post(self):
		"""Test that custom permission types are applied correctly."""
		user_role = "Website Manager"
		doc_type = "Web Page"
		ptype_name = "approve"

		user = self._create_test_user("test_approve_permission@example.com", user_role)

		ptype_doc = self._create_permission_type(ptype_name, doc_type)

		try:
			self._verify_custom_fields_created(ptype_doc, doc_type)

			self._verify_user_lacks_permission(doc_type, ptype_name, user.name)

			update_permission_property(
				doctype=doc_type, role=user_role, permlevel=0, ptype=ptype_name, value=1
			)

			self._verify_user_has_permission(doc_type, ptype_name, user.name)

			update_permission_property(
				doctype=doc_type, role=user_role, permlevel=0, ptype=ptype_name, value=0
			)

		finally:
			frappe.delete_doc("User", user.name, force=True)
			frappe.delete_doc("Permission Type", ptype_doc.name, force=True)

	def test_permission_type_creation_reserved_name(self):
		"""Test that permission types with reserved names are rejected."""
		doc = frappe.get_doc(
			{
				"doctype": "Permission Type",
				"perm_type": "read",
				"doc_type": "ToDo",
				"module": "Core",
			}
		)

		with self.assertRaises(frappe.exceptions.ValidationError):
			doc.insert()

	def _create_test_user(self, email, role):
		"""Create a test user with the specified role."""
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = email.split("@", 1)[0]
		user.insert(ignore_if_duplicate=True)
		user.reload()
		user.add_roles(role)
		return user

	def _create_permission_type(self, name, doc_type):
		"""Create a permission type for the specified doctype."""
		ptype_doc = frappe.get_doc(
			{
				"doctype": "Permission Type",
				"perm_type": name,
				"doc_type": doc_type,
				"module": "Core",
			}
		)
		ptype_doc.insert(ignore_if_duplicate=True)
		ptype_doc.reload()
		return ptype_doc

	def _verify_custom_fields_created(self, ptype_doc, doc_type):
		"""Verify that custom fields are created for the permission type."""
		for target in ["Custom DocPerm", "DocPerm", "DocShare"]:
			custom_field = frappe.get_doc("Custom Field", {"dt": target, "fieldname": ptype_doc.perm_type})
			self.assertEqual(custom_field.dt, target)
			self.assertEqual(custom_field.fieldname, ptype_doc.perm_type)
			self.assertEqual(custom_field.fieldtype, "Check")
			self.assertIn(doc_type, custom_field.depends_on)

	def _verify_user_lacks_permission(self, doc_type, ptype_name, user_name):
		"""Verify that user does not have the specified permission type."""
		self.assertFalse(frappe.has_permission(doc_type, ptype=ptype_name, user=user_name))

	def _verify_user_has_permission(self, doc_type, ptype_name, user_name):
		"""Verify that user has the specified permission type."""
		self.assertTrue(frappe.has_permission(doc_type, ptype=ptype_name, user=user_name))
