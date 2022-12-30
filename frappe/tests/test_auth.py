# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import time

import requests

import frappe
import frappe.utils
from frappe.auth import LoginAttemptTracker
from frappe.frappeclient import AuthError, FrappeClient
from frappe.tests.utils import FrappeTestCase
from frappe.www.login import _generate_temporary_login_link


def add_user(email, password, username=None, mobile_no=None):
	first_name = email.split("@", 1)[0]
	user = frappe.get_doc(
		dict(doctype="User", email=email, first_name=first_name, username=username, mobile_no=mobile_no)
	).insert()
	user.new_password = password
	user.add_roles("System Manager")
	frappe.db.commit()


class TestAuth(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.HOST_NAME = frappe.get_site_config().host_name or frappe.utils.get_site_url(
			frappe.local.site
		)
		cls.test_user_email = "test_auth@test.com"
		cls.test_user_name = "test_auth_user"
		cls.test_user_mobile = "+911234567890"
		cls.test_user_password = "pwd_012"

		cls.tearDownClass()
		add_user(
			email=cls.test_user_email,
			password=cls.test_user_password,
			username=cls.test_user_name,
			mobile_no=cls.test_user_mobile,
		)

	@classmethod
	def tearDownClass(cls):
		frappe.delete_doc("User", cls.test_user_email, force=True)
		frappe.local.request_ip = None
		frappe.form_dict.email = None
		frappe.local.response["http_status_code"] = None

	def set_system_settings(self, k, v):
		frappe.db.set_value("System Settings", "System Settings", k, v)
		frappe.clear_cache()
		frappe.db.commit()

	def test_allow_login_using_mobile(self):
		self.set_system_settings("allow_login_using_mobile_number", 1)
		self.set_system_settings("allow_login_using_user_name", 0)

		# Login by both email and mobile should work
		FrappeClient(self.HOST_NAME, self.test_user_mobile, self.test_user_password)
		FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)

		# login by username should fail
		with self.assertRaises(AuthError):
			FrappeClient(self.HOST_NAME, self.test_user_name, self.test_user_password)

	def test_allow_login_using_only_email(self):
		self.set_system_settings("allow_login_using_mobile_number", 0)
		self.set_system_settings("allow_login_using_user_name", 0)

		# Login by mobile number should fail
		with self.assertRaises(AuthError):
			FrappeClient(self.HOST_NAME, self.test_user_mobile, self.test_user_password)

		# login by username should fail
		with self.assertRaises(AuthError):
			FrappeClient(self.HOST_NAME, self.test_user_name, self.test_user_password)

		# Login by email should work
		FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)

	def test_allow_login_using_username(self):
		self.set_system_settings("allow_login_using_mobile_number", 0)
		self.set_system_settings("allow_login_using_user_name", 1)

		# Mobile login should fail
		with self.assertRaises(AuthError):
			FrappeClient(self.HOST_NAME, self.test_user_mobile, self.test_user_password)

		# Both email and username logins should work
		FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)
		FrappeClient(self.HOST_NAME, self.test_user_name, self.test_user_password)

	def test_allow_login_using_username_and_mobile(self):
		self.set_system_settings("allow_login_using_mobile_number", 1)
		self.set_system_settings("allow_login_using_user_name", 1)

		# Both email and username and mobile logins should work
		FrappeClient(self.HOST_NAME, self.test_user_mobile, self.test_user_password)
		FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)
		FrappeClient(self.HOST_NAME, self.test_user_name, self.test_user_password)

	def test_deny_multiple_login(self):
		self.set_system_settings("deny_multiple_sessions", 1)
		self.addCleanup(self.set_system_settings, "deny_multiple_sessions", 0)

		first_login = FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)
		first_login.get_list("ToDo")

		second_login = FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)
		second_login.get_list("ToDo")
		with self.assertRaises(Exception):
			first_login.get_list("ToDo")

		third_login = FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)
		with self.assertRaises(Exception):
			first_login.get_list("ToDo")
		with self.assertRaises(Exception):
			second_login.get_list("ToDo")
		third_login.get_list("ToDo")

	def test_disable_user_pass_login(self):
		FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password).get_list("ToDo")
		self.set_system_settings("disable_user_pass_login", 1)
		self.addCleanup(self.set_system_settings, "disable_user_pass_login", 0)

		with self.assertRaises(Exception):
			FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password).get_list("ToDo")

	def test_login_with_email_link(self):

		user = self.test_user_email

		# Logs in
		res = requests.get(_generate_temporary_login_link(user, 10))
		self.assertEqual(res.status_code, 200)
		self.assertTrue(res.cookies.get("sid"))
		self.assertNotEqual(res.cookies.get("sid"), "Guest")

		# Random incorrect URL
		res = requests.get(_generate_temporary_login_link(user, 10) + "aa")
		self.assertEqual(res.cookies.get("sid"), "Guest")

		# POST doesn't work
		res = requests.post(_generate_temporary_login_link(user, 10))
		self.assertEqual(res.status_code, 403)

		# Rate limiting
		for _ in range(6):
			res = requests.get(_generate_temporary_login_link(user, 10))
			if res.status_code == 417:
				break
		else:
			self.fail("Rate limting not working")


class TestLoginAttemptTracker(FrappeTestCase):
	def test_account_lock(self):
		"""Make sure that account locks after `n consecutive failures"""
		tracker = LoginAttemptTracker(
			user_name="tester", max_consecutive_login_attempts=3, lock_interval=60
		)
		# Clear the cache by setting attempt as success
		tracker.add_success_attempt()

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())

		tracker.add_failure_attempt()
		self.assertFalse(tracker.is_user_allowed())

	def test_account_unlock(self):
		"""Make sure that locked account gets unlocked after lock_interval of time."""
		lock_interval = 2  # In sec
		tracker = LoginAttemptTracker(
			user_name="tester", max_consecutive_login_attempts=1, lock_interval=lock_interval
		)
		# Clear the cache by setting attempt as success
		tracker.add_success_attempt()

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())

		tracker.add_failure_attempt()
		self.assertFalse(tracker.is_user_allowed())

		# Sleep for lock_interval of time, so that next request con unlock the user access.
		time.sleep(lock_interval)

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())
