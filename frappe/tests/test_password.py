# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals
import frappe
import unittest
from frappe.utils.password import update_password, check_password

class TestPassword(unittest.TestCase):
	def setUp(self):
		frappe.delete_doc('Email Account', 'Test Email Account Password')
		frappe.delete_doc('Email Account', 'Test Email Account Password-new')

	def test_encrypted_password(self):
		doc = self.make_email_account()

		new_password = 'test-password'
		doc.password = new_password
		doc.save()

		self.assertEquals(doc.password, '*'*len(new_password))

		auth_password = frappe.db.sql('''select `password` from `__Auth`
			where doctype=%(doctype)s and name=%(name)s and fieldname="password"''', doc.as_dict())[0][0]

		# encrypted
		self.assertTrue(auth_password != new_password)

		# decrypted
		self.assertEquals(doc.get_password(), new_password)

		return doc, new_password

	def make_email_account(self, name='Test Email Account Password'):
		if not frappe.db.exists('Email Account', name):
			return frappe.get_doc({
				'doctype': 'Email Account',
				'domain': 'example.com',
				'email_account_name': name,
				'append_to': 'Communication',
				'smtp_server': 'test.example.com',
				'pop3_server': 'pop.test.example.com',
				'email_id': 'test-password@example.com',
				'password': 'password',
			}).insert()

		else:
			return frappe.get_doc('Email Account', name)

	def test_hashed_password(self, user='test@example.com'):
		old_password = 'Eastern_43A1W'
		new_password = 'Eastern_43A1W-new'

		update_password(user, new_password)

		auth = frappe.db.sql('''select `password`, `salt` from `__Auth`
			where doctype='User' and name=%s and fieldname="password"''', user, as_dict=True)[0]

		self.assertTrue(auth.password != new_password)
		self.assertTrue(auth.salt)

		# stored password = password(plain_text_password + salt)
		self.assertEquals(frappe.db.sql('select password(concat(%s, %s))', (new_password, auth.salt))[0][0], auth.password)

		self.assertTrue(check_password(user, new_password))

		# revert back to old
		update_password(user, old_password)
		self.assertTrue(check_password(user, old_password))

		# shouldn't work with old password
		self.assertRaises(frappe.AuthenticationError, check_password, user, new_password)

	def test_password_on_rename_user(self):
		password = 'test-rename-password'

		doc = self.make_email_account()
		doc.password = password
		doc.save()

		old_name = doc.name
		new_name = old_name + '-new'
		frappe.rename_doc(doc.doctype, old_name, new_name)

		new_doc = frappe.get_doc(doc.doctype, new_name)
		self.assertEquals(new_doc.get_password(), password)
		self.assertTrue(not frappe.db.sql('''select `password` from `__Auth`
			where doctype=%s and name=%s and fieldname="password"''', (doc.doctype, doc.name)))

		frappe.rename_doc(doc.doctype, new_name, old_name)
		self.assertTrue(frappe.db.sql('''select `password` from `__Auth`
			where doctype=%s and name=%s and fieldname="password"''', (doc.doctype, doc.name)))

	def test_password_on_delete(self):
		doc = self.make_email_account()
		doc.delete()

		self.assertTrue(not frappe.db.sql('''select `password` from `__Auth`
			where doctype=%s and name=%s and fieldname="password"''', (doc.doctype, doc.name)))

