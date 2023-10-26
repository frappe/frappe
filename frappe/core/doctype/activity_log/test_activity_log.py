# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import time

import frappe
from frappe.auth import CookieManager, LoginManager
from frappe.tests.utils import FrappeTestCase


class TestActivityLog(FrappeTestCase):
	def test_activity_log(self):

		# test user login log
		frappe.local.form_dict = frappe._dict(
			{
				"cmd": "login",
				"sid": "Guest",
				"pwd": frappe.conf.admin_password or "admin",
				"usr": "Administrator",
			}
		)

		frappe.local.request_ip = "127.0.0.1"
		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()

		auth_log = self.get_auth_log()
		self.assertFalse(frappe.form_dict.pwd)
		self.assertEqual(auth_log.status, "Success")

		# test user logout log
		frappe.local.login_manager.logout()
		auth_log = self.get_auth_log(operation="Logout")
		self.assertEqual(auth_log.status, "Success")

		# test invalid login
		frappe.form_dict.update({"pwd": "password"})
		self.assertRaises(frappe.AuthenticationError, LoginManager)
		auth_log = self.get_auth_log()
		self.assertEqual(auth_log.status, "Failed")

		frappe.local.form_dict = frappe._dict()

	def get_auth_log(self, operation="Login"):
		names = frappe.get_all(
			"Activity Log",
			filters={
				"user": "Administrator",
				"operation": operation,
			},
			order_by="`creation` DESC",
		)

		name = names[0]
		auth_log = frappe.get_doc("Activity Log", name)
		return auth_log

	def test_brute_security(self):
		update_system_settings({"allow_consecutive_login_attempts": 3, "allow_login_after_fail": 5})

		frappe.local.form_dict = frappe._dict(
			{"cmd": "login", "sid": "Guest", "pwd": "admin", "usr": "Administrator"}
		)

		frappe.local.request_ip = "127.0.0.1"
		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()

		auth_log = self.get_auth_log()
		self.assertEqual(auth_log.status, "Success")

		# test user logout log
		frappe.local.login_manager.logout()
		auth_log = self.get_auth_log(operation="Logout")
		self.assertEqual(auth_log.status, "Success")

		# test invalid login
		frappe.form_dict.update({"pwd": "password"})
		self.assertRaises(frappe.AuthenticationError, LoginManager)
		self.assertRaises(frappe.AuthenticationError, LoginManager)
		self.assertRaises(frappe.AuthenticationError, LoginManager)

		# REMOVE ME: current logic allows allow_consecutive_login_attempts+1 attempts
		# before raising security exception, remove below line when that is fixed.
		self.assertRaises(frappe.AuthenticationError, LoginManager)
		self.assertRaises(frappe.SecurityException, LoginManager)
		time.sleep(5)
		self.assertRaises(frappe.AuthenticationError, LoginManager)

		frappe.local.form_dict = frappe._dict()


def update_system_settings(args):
	doc = frappe.get_doc("System Settings")
	doc.update(args)
	doc.flags.ignore_mandatory = 1
	doc.save()
