# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import time
import unittest

import frappe
from frappe.auth import HTTPRequest, LoginAttemptTracker
from frappe.frappeclient import AuthError, FrappeClient
from frappe.utils import set_request


class TestAuth(unittest.TestCase):
	def __init__(self, *args, **kwargs):
		super(TestAuth, self).__init__(*args, **kwargs)
		self.test_user_email = "test_auth@test.com"
		self.test_user_name = "test_auth_user"
		self.test_user_mobile = "+911234567890"
		self.test_user_password = "pwd_012"

	def setUp(self):
		self.tearDown()

		self.add_user(
			self.test_user_email,
			self.test_user_password,
			username=self.test_user_name,
			mobile_no=self.test_user_mobile,
		)

	def tearDown(self):
		frappe.delete_doc("User", self.test_user_email, force=True)

	def add_user(self, email, password, username=None, mobile_no=None):
		first_name = email.split("@", 1)[0]
		user = frappe.get_doc(
			dict(doctype="User", email=email, first_name=first_name, username=username, mobile_no=mobile_no)
		).insert()
		user.new_password = password
		user.save()
		frappe.db.commit()

	def set_system_settings(self, k, v):
		frappe.db.set_value("System Settings", "System Settings", k, v)
		frappe.db.commit()

	def test_allow_login_using_mobile(self):
		self.set_system_settings("allow_login_using_mobile_number", 1)
		self.set_system_settings("allow_login_using_user_name", 0)

		# Login by both email and mobile should work
		FrappeClient(frappe.get_site_config().host_name, self.test_user_mobile, self.test_user_password)
		FrappeClient(frappe.get_site_config().host_name, self.test_user_email, self.test_user_password)

		# login by username should fail
		with self.assertRaises(AuthError):
			FrappeClient(frappe.get_site_config().host_name, self.test_user_name, self.test_user_password)

	def test_allow_login_using_only_email(self):
		self.set_system_settings("allow_login_using_mobile_number", 0)
		self.set_system_settings("allow_login_using_user_name", 0)

		# Login by mobile number should fail
		with self.assertRaises(AuthError):
			FrappeClient(frappe.get_site_config().host_name, self.test_user_mobile, self.test_user_password)

		# login by username should fail
		with self.assertRaises(AuthError):
			FrappeClient(frappe.get_site_config().host_name, self.test_user_name, self.test_user_password)

		# Login by email should work
		FrappeClient(frappe.get_site_config().host_name, self.test_user_email, self.test_user_password)

	def test_allow_login_using_username(self):
		self.set_system_settings("allow_login_using_mobile_number", 0)
		self.set_system_settings("allow_login_using_user_name", 1)

		# Mobile login should fail
		with self.assertRaises(AuthError):
			FrappeClient(frappe.get_site_config().host_name, self.test_user_mobile, self.test_user_password)

		# Both email and username logins should work
		FrappeClient(frappe.get_site_config().host_name, self.test_user_email, self.test_user_password)
		FrappeClient(frappe.get_site_config().host_name, self.test_user_name, self.test_user_password)

	def test_allow_login_using_username_and_mobile(self):
		self.set_system_settings("allow_login_using_mobile_number", 1)
		self.set_system_settings("allow_login_using_user_name", 1)

		# Both email and username and mobile logins should work
		FrappeClient(frappe.get_site_config().host_name, self.test_user_mobile, self.test_user_password)
		FrappeClient(frappe.get_site_config().host_name, self.test_user_email, self.test_user_password)
		FrappeClient(frappe.get_site_config().host_name, self.test_user_name, self.test_user_password)


class TestLoginAttemptTracker(unittest.TestCase):
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
