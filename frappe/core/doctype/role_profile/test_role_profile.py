# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals
import frappe
import unittest

class TestRoleProfile(unittest.TestCase):
	def test_make_new_role_profile(self):
		new_role_profile = frappe.get_doc(dict(doctype='Role Profile', role_profile='Test 1')).insert()

		self.assertEqual(new_role_profile.role_profile, 'Test 1')

		# add role
		new_role_profile.append("roles", {
			"role": '_Test Role 2'
		})
		new_role_profile.save()
		self.assertEqual(new_role_profile.roles[0].role, '_Test Role 2')

		# clear roles
		new_role_profile.roles = []
		new_role_profile.save()
		self.assertEqual(new_role_profile.roles, [])