# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest

import frappe
from frappe.utils.password import check_password, passlibctx, update_password


class TestPassword(unittest.TestCase):
	def setUp(self):
		frappe.delete_doc("Email Account", "Test Email Account Password")
		frappe.delete_doc("Email Account", "Test Email Account Password-new")

	def test_encrypted_password(self):
		doc = self.make_email_account()

		new_password = "test-password"
		doc.password = new_password
		doc.save()

		self.assertEqual(doc.password, "*" * len(new_password))

		password_list = get_password_list(doc)

		auth_password = password_list[0].get("password", "")

		# encrypted
		self.assertTrue(auth_password != new_password)

		# decrypted
		self.assertEqual(doc.get_password(), new_password)

		return doc, new_password

	def make_email_account(self, name="Test Email Account Password"):
		if not frappe.db.exists("Email Account", name):
			return frappe.get_doc(
				{
					"doctype": "Email Account",
					"domain": "example.com",
					"email_account_name": name,
					"append_to": "Communication",
					"smtp_server": "test.example.com",
					"pop3_server": "pop.test.example.com",
					"email_id": "test-password@example.com",
					"password": "password",
				}
			).insert()

		else:
			return frappe.get_doc("Email Account", name)

	def test_hashed_password(self, user="test@example.com"):
		old_password = "Eastern_43A1W"
		new_password = "Eastern_43A1W-new"

		update_password(user, new_password)

		auth = get_password_list(dict(doctype="User", name=user))[0]

		# is not plain text
		self.assertTrue(auth.password != new_password)

		# is valid hashing
		self.assertTrue(passlibctx.verify(new_password, auth.password))

		self.assertTrue(check_password(user, new_password))

		# revert back to old
		update_password(user, old_password)
		self.assertTrue(check_password(user, old_password))

		# shouldn't work with old password
		self.assertRaises(frappe.AuthenticationError, check_password, user, new_password)

	def test_password_on_rename_user(self):
		password = "test-rename-password"

		doc = self.make_email_account()
		doc.password = password
		doc.save()

		old_name = doc.name
		new_name = old_name + "-new"
		frappe.rename_doc(doc.doctype, old_name, new_name)

		new_doc = frappe.get_doc(doc.doctype, new_name)
		self.assertEqual(new_doc.get_password(), password)
		self.assertTrue(not get_password_list(doc))

		frappe.rename_doc(doc.doctype, new_name, old_name)
		self.assertTrue(get_password_list(doc))

	def test_password_on_delete(self):
		doc = self.make_email_account()
		doc.delete()

		self.assertTrue(not get_password_list(doc))

	def test_password_unset(self):
		doc = self.make_email_account()

		doc.password = "asdf"
		doc.save()
		self.assertEqual(doc.get_password(raise_exception=False), "asdf")

		doc.password = ""
		doc.save()
		self.assertEqual(doc.get_password(raise_exception=False), None)


def get_password_list(doc):
	return frappe.db.sql(
		"""SELECT `password`
			FROM `__Auth`
			WHERE `doctype`=%s
			AND `name`=%s
			AND `fieldname`='password' LIMIT 1""",
		(doc.get("doctype"), doc.get("name")),
		as_dict=1,
	)
