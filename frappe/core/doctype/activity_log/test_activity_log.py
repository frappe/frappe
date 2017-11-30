# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

class TestActivityLog(unittest.TestCase):
	def test_activity_log(self):
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
		names = frappe.db.sql_list("""select name from `tabActivity Log`
					where user='Administrator' and operation='{operation}' order by
					creation desc""".format(operation=operation))

		name = names[0]
		auth_log = frappe.get_doc('Activity Log', name)
		return auth_log