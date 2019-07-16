# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import time
import unittest

from frappe.core.doctype.session.session import (login, get_session, SessionExpiredError,
	InvalidIPError, InvalidLoginHour, TooManyFailedLogins)

class TestSession(unittest.TestCase):
	def test_login(self):
		user = get_user('user1@example.com', 'pass1')
		session = login('user1@example.com', 'pass1')
		self.assertEqual(session.status, "Active")
		self.assertRaises(frappe.AuthenticationError, login, 'user1@example.com', 'pass3')
		self.assertRaises(frappe.AuthenticationError, login, 'failuser1@example.com', 'pass3')

	def test_logout(self):
		user = get_user('user1@example.com', 'pass1')
		session = login('user1@example.com', 'pass1')
		session.logout()
		self.assertRaises(SessionExpiredError, get_session, sid = session.name)

	def test_disabled(self):
		user = get_user('user_disabled@example.com', 'pass4', dict(enabled=0))
		frappe.db.set_value('User', 'user_disabled@example.com', 'enabled', 0)
		self.assertRaises(frappe.AuthenticationError, login, 'user_disabled@example.com', 'pass4')

	def test_ip_restriction(self):
		user = get_user('user_ip_restricted@example.com', 'pass1', dict(restrict_ip='5.5.5.5,10.10.10.10'))
		frappe.local.request_ip = '5.5.5.5'
		session = login('user_ip_restricted@example.com', 'pass1')
		self.assertEqual(session.status, "Active")

		frappe.local.request_ip = '15.5.5.5'
		self.assertRaises(InvalidIPError, login, 'user_ip_restricted@example.com', 'pass1')

	def test_login_before_after_restriction(self):
		### BEFORE
		user = get_user('user_restricted_before@example.com', 'pass1', dict(login_before=18))

		# logs in at valid hour
		frappe.flags.test_current_hour = 10
		session = login('user_restricted_before@example.com', 'pass1')
		self.assertEqual(session.status, "Active")

		# logs in late
		frappe.flags.test_current_hour = 20
		self.assertRaises(InvalidLoginHour, login, 'user_restricted_before@example.com', 'pass1')

		### AFTER
		user = get_user('user_restricted_after@example.com', 'pass1', dict(login_after=9))

		# logs in at valid hour
		frappe.flags.test_current_hour = 10
		session = login('user_restricted_after@example.com', 'pass1')
		self.assertEqual(session.status, "Active")

		# logs in early
		frappe.flags.test_current_hour = 8
		self.assertRaises(InvalidLoginHour, login, 'user_restricted_after@example.com', 'pass1')

	def test_too_failed_many_logins(self):
		system_settings = frappe.get_doc('System Settings')
		system_settings.allow_consecutive_login_attempts = 3
		system_settings.allow_login_after_fail = 3
		system_settings.save()

		user = get_user('user1@example.com', 'pass1')

		# try to lock out
		self.assertRaises(frappe.AuthenticationError, login, 'user1@example.com', 'pass3')
		self.assertRaises(frappe.AuthenticationError, login, 'user1@example.com', 'pass3')
		self.assertRaises(frappe.AuthenticationError, login, 'user1@example.com', 'pass3')
		self.assertRaises(TooManyFailedLogins, login, 'user1@example.com', 'pass3')

		# try correct password too
		self.assertRaises(TooManyFailedLogins, login, 'user1@example.com', 'pass1')

		time.sleep(3)

		# allowed after cool down period
		session = login('user1@example.com', 'pass1')
		self.assertEqual(session.status, "Active")

		system_settings.allow_consecutive_login_attempts = 0
		system_settings.save()

	def test_deny_multiple_sessions(self):
		system_settings = frappe.get_doc('System Settings')
		system_settings.deny_multiple_sessions = 1
		system_settings.save()

		user = get_user('user1@example.com', 'pass1')

		# try to lock out
		session1 = login('user1@example.com', 'pass1')
		session2 = login('user1@example.com', 'pass1')

		self.assertEqual(session1.get_status(), 'Expired')
		self.assertEqual(session2.get_status(), 'Active')

		# allow 3 sessions sessions
		frappe.db.set_value('User', 'user1@example.com', 'simultaneous_sessions', 3)

		session1 = login('user1@example.com', 'pass1')
		session2 = login('user1@example.com', 'pass1')
		session3 = login('user1@example.com', 'pass1')
		session4 = login('user1@example.com', 'pass1')

		# only first status expired
		self.assertEqual(session1.get_status(), 'Expired')
		self.assertEqual(session2.get_status(), 'Active')
		self.assertEqual(session3.get_status(), 'Active')
		self.assertEqual(session4.get_status(), 'Active')

		system_settings.deny_multiple_sessions = 0
		system_settings.save()


def get_user(name, password, properties=None):
	if frappe.db.exists('User', name):
		return frappe.get_doc('User', name)
	else:
		user = frappe.new_doc('User')
		user.email = name
		user.first_name = name.split("@")[0]
		user.new_password = password
		if properties:
			user.update(properties)
		user.add_roles("System Manager")
	return user


