# Copyright (c) 2015, nts Technologies and Contributors
# License: MIT. See LICENSE
import time

import nts
from nts.auth import CookieManager, LoginManager
from nts.tests.utils import ntsTestCase


class TestActivityLog(ntsTestCase):
	def setUp(self) -> None:
		nts.set_user("Administrator")

	def test_activity_log(self):
		# test user login log
		nts.local.form_dict = nts._dict(
			{
				"cmd": "login",
				"sid": "Guest",
				"pwd": self.ADMIN_PASSWORD or "admin",
				"usr": "Administrator",
			}
		)

		nts.local.request_ip = "127.0.0.1"
		nts.local.cookie_manager = CookieManager()
		nts.local.login_manager = LoginManager()

		auth_log = self.get_auth_log()
		self.assertFalse(nts.form_dict.pwd)
		self.assertEqual(auth_log.status, "Success")

		# test user logout log
		nts.local.login_manager.logout()
		auth_log = self.get_auth_log(operation="Logout")
		self.assertEqual(auth_log.status, "Success")

		# test invalid login
		nts.form_dict.update({"pwd": "password"})
		self.assertRaises(nts.AuthenticationError, LoginManager)
		auth_log = self.get_auth_log()
		self.assertEqual(auth_log.status, "Failed")

		nts.local.form_dict = nts._dict()

	def get_auth_log(self, operation="Login"):
		names = nts.get_all(
			"Activity Log",
			filters={
				"user": "Administrator",
				"operation": operation,
			},
			order_by="`creation` DESC",
		)

		name = names[0]
		return nts.get_doc("Activity Log", name)

	def test_brute_security(self):
		update_system_settings({"allow_consecutive_login_attempts": 3, "allow_login_after_fail": 5})

		nts.local.form_dict = nts._dict(
			{"cmd": "login", "sid": "Guest", "pwd": self.ADMIN_PASSWORD, "usr": "Administrator"}
		)

		nts.local.request_ip = "127.0.0.1"
		nts.local.cookie_manager = CookieManager()
		nts.local.login_manager = LoginManager()

		auth_log = self.get_auth_log()
		self.assertEqual(auth_log.status, "Success")

		# test user logout log
		nts.local.login_manager.logout()
		auth_log = self.get_auth_log(operation="Logout")
		self.assertEqual(auth_log.status, "Success")

		# test invalid login
		nts.form_dict.update({"pwd": "password"})
		self.assertRaises(nts.AuthenticationError, LoginManager)
		self.assertRaises(nts.AuthenticationError, LoginManager)
		self.assertRaises(nts.AuthenticationError, LoginManager)

		# REMOVE ME: current logic allows allow_consecutive_login_attempts+1 attempts
		# before raising security exception, remove below line when that is fixed.
		self.assertRaises(nts.AuthenticationError, LoginManager)
		self.assertRaises(nts.SecurityException, LoginManager)
		time.sleep(5)
		self.assertRaises(nts.AuthenticationError, LoginManager)

		nts.local.form_dict = nts._dict()


def update_system_settings(args):
	doc = nts.get_doc("System Settings")
	doc.update(args)
	doc.flags.ignore_mandatory = 1
	doc.save()
