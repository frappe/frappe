# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import time
import unittest

import frappe
from frappe.auth import LoginAttemptTracker
from frappe.frappeclient import FrappeClient


class TestAuth(unittest.TestCase):
	def test_admin_login(self):
		# Make sure that authentication works when allow_login_using_mobile_number is set to 0
		frappe.db.set_value("System Settings", "System Settings", "allow_login_using_mobile_number", 0)
		frappe.db.commit()
		FrappeClient(frappe.get_site_config().host_name, "Administrator", "admin", verify=False)

		# Make sure that authentication works when allow_login_using_mobile_number is set to 1
		frappe.db.set_value("System Settings", "System Settings", "allow_login_using_mobile_number", 1)
		frappe.db.commit()
		FrappeClient(frappe.get_site_config().host_name, "Administrator", "admin", verify=False)


class TestLoginAttemptTracker(unittest.TestCase):
	def test_account_lock(self):
		"""Make sure that account locks after `n consecutive failures
		"""
		tracker = LoginAttemptTracker(user_name='tester', max_consecutive_login_attempts=3, lock_interval=60)
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
		"""Make sure that locked account gets unlocked after lock_interval of time.
		"""
		lock_interval = 10 # In sec
		tracker = LoginAttemptTracker(user_name='tester', max_consecutive_login_attempts=1, lock_interval=lock_interval)
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
