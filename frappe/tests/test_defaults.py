# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.user_permission.test_user_permission import create_user
from frappe.defaults import *
from frappe.tests import IntegrationTestCase


class TestDefaults(IntegrationTestCase):
	def test_global(self):
		clear_user_default("key1")
		set_global_default("key1", "value1")
		self.assertEqual(get_global_default("key1"), "value1")

		set_global_default("key1", "value2")
		self.assertEqual(get_global_default("key1"), "value2")

		add_global_default("key1", "value3")
		self.assertEqual(get_global_default("key1"), "value2")
		self.assertEqual(get_defaults()["key1"], ["value2", "value3"])
		self.assertEqual(get_user_default_as_list("key1"), ["value2", "value3"])

	def test_user(self):
		set_user_default("key1", "2value1")
		self.assertEqual(get_user_default_as_list("key1"), ["2value1"])

		set_user_default("key1", "2value2")
		self.assertEqual(get_user_default("key1"), "2value2")

		add_user_default("key1", "3value3")
		self.assertEqual(get_user_default("key1"), "2value2")
		self.assertEqual(get_user_default_as_list("key1"), ["2value2", "3value3"])

	def test_global_if_not_user(self):
		set_global_default("key4", "value4")
		self.assertEqual(get_user_default("key4"), "value4")

	def test_clear(self):
		set_user_default("key5", "value5")
		self.assertEqual(get_user_default("key5"), "value5")
		clear_user_default("key5")
		self.assertEqual(get_user_default("key5"), None)

	def test_clear_global(self):
		set_global_default("key6", "value6")
		self.assertEqual(get_user_default("key6"), "value6")

		clear_default("key6", value="value6")
		self.assertEqual(get_user_default("key6"), None)

	def test_user_permission_on_defaults(self):
		self.assertEqual(get_global_default("language"), "en")
		self.assertEqual(get_user_default("language"), "en")
		self.assertEqual(get_user_default_as_list("language"), ["en"])

		old_user = frappe.session.user
		user = "test@example.com"
		frappe.set_user(user)

		perm_doc = frappe.get_doc(
			doctype="User Permission", user=frappe.session.user, allow="Language", for_value="en-GB"
		).insert(ignore_permissions=True)

		self.assertEqual(get_global_default("language"), None)
		self.assertEqual(get_user_default("language"), None)
		self.assertEqual(get_user_default_as_list("language"), [])

		frappe.delete_doc("User Permission", perm_doc.name)
		frappe.set_user(old_user)

	def test_user_permission_defaults(self):
		user = "user_default_test@example.com"
		create_user(user, "Website Manager")

		with self.set_user(user):
			set_global_default("country", "United States")
			set_global_default("Country", "")
			clear_user_default("Country")
			clear_user_default("country")

			perm_doc = frappe.get_doc(
				doctype="User Permission", user=user, allow="Country", for_value="India"
			).insert(ignore_permissions=True)

			perm_doc.is_default = 1
			perm_doc.save(ignore_permissions=True)
			set_global_default("Country", "United States")
			self.assertEqual(get_user_default("Country"), "India")

			perm_doc.is_default = 0
			perm_doc.save(ignore_permissions=True)
			clear_user_default("Country")
			self.assertEqual(get_user_default("Country"), None)

			frappe.get_doc(
				doctype="User Permission", user=user, allow="Country", for_value="United States"
			).insert(ignore_permissions=True)

			self.assertEqual(get_user_default("Country"), "United States")

			# a permitted default chosen by the user beats the User Permission default
			perm_doc.is_default = 1
			perm_doc.save(ignore_permissions=True)
			set_user_default("country", "United States")
			self.assertEqual(get_user_default("Country"), "United States")
