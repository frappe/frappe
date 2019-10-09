# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import time
from frappe.auth import LoginManager, CookieManager

class TestActivityLog(unittest.TestCase):
	def test_activity_log(self):

		# test user login log
		frappe.local.form_dict = frappe._dict({
			'cmd': 'login',
			'sid': 'Guest',
			'pwd': 'admin',
			'usr': 'Administrator'
		})

		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()

		auth_log = self.get_auth_log()
		self.assertEqual(auth_log.status, 'Success')

		# test user logout log
		frappe.local.login_manager.logout()
		auth_log = self.get_auth_log(operation='Logout')
		self.assertEqual(auth_log.status, 'Success')

		# test invalid login
		frappe.form_dict.update({ 'pwd': 'password' })
		self.assertRaises(frappe.AuthenticationError, LoginManager)
		auth_log = self.get_auth_log()
		self.assertEqual(auth_log.status, 'Failed')

		frappe.local.form_dict = frappe._dict()

	def get_auth_log(self, operation='Login'):
		names = frappe.db.get_all('Activity Log', filters={
			'user': 'Administrator',
			'operation': operation,
		}, order_by='`creation` DESC')

		name = names[0]
		auth_log = frappe.get_doc('Activity Log', name)
		return auth_log

	def test_brute_security(self):
		update_system_settings({
			'allow_consecutive_login_attempts': 3,
			'allow_login_after_fail': 5
		})

		frappe.local.form_dict = frappe._dict({
			'cmd': 'login',
			'sid': 'Guest',
			'pwd': 'admin',
			'usr': 'Administrator'
		})

		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()

		auth_log = self.get_auth_log()
		self.assertEquals(auth_log.status, 'Success')

		# test user logout log
		frappe.local.login_manager.logout()
		auth_log = self.get_auth_log(operation='Logout')
		self.assertEquals(auth_log.status, 'Success')

		# test invalid login
		frappe.form_dict.update({ 'pwd': 'password' })
		self.assertRaises(frappe.AuthenticationError, LoginManager)
		self.assertRaises(frappe.AuthenticationError, LoginManager)
		self.assertRaises(frappe.AuthenticationError, LoginManager)
		self.assertRaises(frappe.SecurityException, LoginManager)
		time.sleep(5)
		self.assertRaises(frappe.AuthenticationError, LoginManager)

		frappe.local.form_dict = frappe._dict()

def update_system_settings(args):
	doc = frappe.get_doc('System Settings')
	doc.update(args)
	doc.save()
