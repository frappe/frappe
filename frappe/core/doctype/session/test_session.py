# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

from frappe.core.doctype.session.session import (get_session, SessionExpiredError,
	InvalidIPError, InvalidLoginHour)

class TestSession(unittest.TestCase):
	def test_login(self):
		user = get_user('user1@example.com', 'pass1')
		session = get_session('user1@example.com', 'pass1')
		self.assertEqual(session.status, "Active")
		self.assertRaises(frappe.AuthenticationError, get_session, 'user1@example.com', 'pass3')
		self.assertRaises(frappe.AuthenticationError, get_session, 'failuser1@example.com', 'pass3')

	def test_logout(self):
		user = get_user('user1@example.com', 'pass1')
		session = get_session('user1@example.com', 'pass1')
		session.logout()
		self.assertRaises(SessionExpiredError, get_session, sid = session.name)

	def test_disabled(self):
		user = get_user('user_disabled@example.com', 'pass4', dict(enabled=0))
		frappe.db.set_value('User', 'user_disabled@example.com', 'enabled', 0)
		self.assertRaises(frappe.AuthenticationError, get_session, 'user_disabled@example.com', 'pass4')

	def test_ip_restriction(self):
		user = get_user('user_ip_restricted@example.com', 'pass1', dict(restrict_ip='5.5.5.5,10.10.10.10'))
		frappe.local.request_ip = '5.5.5.5'
		session = get_session('user_ip_restricted@example.com', 'pass1')
		self.assertEqual(session.status, "Active")

		frappe.local.request_ip = '15.5.5.5'
		self.assertRaises(InvalidIPError, get_session, 'user_ip_restricted@example.com', 'pass1')

	def test_login_before_after_restriction(self):
		### BEFORE
		user = get_user('user_restricted_before@example.com', 'pass1', dict(login_before=18))

		# logs in at valid hour
		frappe.flags.test_current_hour = 10
		session = get_session('user_restricted_before@example.com', 'pass1')
		self.assertEqual(session.status, "Active")

		# logs in late
		frappe.flags.test_current_hour = 20
		self.assertRaises(InvalidLoginHour, get_session, 'user_restricted_before@example.com', 'pass1')

		### AFTER
		user = get_user('user_restricted_after@example.com', 'pass1', dict(login_after=9))

		# logs in at valid hour
		frappe.flags.test_current_hour = 10
		session = get_session('user_restricted_after@example.com', 'pass1')
		self.assertEqual(session.status, "Active")

		# logs in early
		frappe.flags.test_current_hour = 8
		self.assertRaises(InvalidLoginHour, get_session, 'user_restricted_after@example.com', 'pass1')


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


