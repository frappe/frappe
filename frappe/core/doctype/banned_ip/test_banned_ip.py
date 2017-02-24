# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import json
from frappe.auth import LoginManager, CookieManager

class TestBannedIP(unittest.TestCase):
	def setUp(self):
		user = frappe.get_doc('User', 'test@example.com')
		user.enabled = 1
		user.new_password = 'testpassword'
		user.save()

	def test_ban_ip_after_maximum_consecutive_login_failure(self):
		frappe.local.request_ip = '127.0.0.1'

		# test user login log
		frappe.local.form_dict = { 'cmd': 'login' }

		frappe.form_dict = {
			'pwd': 'test123',
			'usr': 'test@example.com'
		}

		cache = frappe.cache()

		for i in range(0, 5):
			try:
				frappe.local.cookie_manager = CookieManager()
				frappe.local.login_manager = LoginManager()
			except frappe.AuthenticationError:
				self.assertEqual(frappe.flags.auth_failed, not frappe.flags.ban_ip)

				if not frappe.flags.ban_ip:
					login_failed_from_ip = json.loads(cache.get("login_failed_from_ip"))
					self.assertEqual(login_failed_from_ip['127.0.0.1'], i+1)

				if frappe.flags.ban_ip:
					self.assertEqual(frappe.db.get_value("Banned IP", {"ip_address": "127.0.0.1"},  "banned"), 1)

	def tearDown(self):
		cache = frappe.cache()
		del cache['login_failed_from_ip']

		frappe.db.sql("delete from `tabBanned IP`")
