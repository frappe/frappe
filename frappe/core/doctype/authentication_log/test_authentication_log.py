# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

# test_records = frappe.get_test_records('Authentication Log')

class TestAuthenticationLog(unittest.TestCase):
	def test_authentication_log(self):
		from frappe.auth import LoginManager, CookieManager

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
		self.assertEquals(auth_log.status, 'Success')

		# test user logout log
		frappe.local.login_manager.logout()
		auth_log = self.get_auth_log(operation='Logout')
		self.assertEquals(auth_log.status, 'Success')

		# test invalid login
		frappe.form_dict.update({ 'pwd': 'password' })
		self.assertRaises(frappe.AuthenticationError, LoginManager)
		auth_log = self.get_auth_log()
		self.assertEquals(auth_log.status, 'Failed')

		frappe.local.form_dict = frappe._dict()

	def get_auth_log(self, operation='Login'):
		names = frappe.db.sql_list("""select name from `tabAuthentication Log`
					where user='Administrator' and operation='{operation}' order by
					creation desc""".format(operation=operation))

		name = names[0]
		auth_log = frappe.get_doc('Authentication Log', name)
		return auth_log