# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals
from frappe.core.doctype.user_permission.user_permission import add_user_permissions

import frappe
import unittest

class TestUserPermission(unittest.TestCase):
	def test_apply_to_all(self):
		''' Create User permission for User having access to all applicable Doctypes'''
		user = get_user()
		param = get_params(user, apply_to_all = 1)
		is_created = add_user_permissions(param)
		self.assertEquals(is_created, 1)

	def test_for_apply_to_all_on_update_from_apply_all(self):
		user = get_user()
		param = get_params(user, apply_to_all=1)

		check = add_user_permissions(param)

		self.assertIsNotNone(check)

		is_created = add_user_permissions(param)
		self.assertEquals(is_created, 0)

	def test_for_applicable_on_update_from_apply_to_all(self):
		''' Update User Permission from all to some applicable Doctypes'''
		user = get_user()
		param = get_params(user, applicable = ["Chat Room", "Chat Message"])

		check = add_user_permissions(get_params(user, apply_to_all= 1))

		self.assertIsNotNone(check)

		is_created = add_user_permissions(param)
		frappe.db.commit()

		removed_apply_to_all = frappe.db.exists("User Permission", get_exists_param(user))
		is_created_applicable_first = frappe.db.exists("User Permission", get_exists_param(user, applicable = "Chat Room"))
		is_created_applicable_second = frappe.db.exists("User Permission", get_exists_param(user, applicable = "Chat Message"))

		self.assertIsNone(removed_apply_to_all)
		self.assertIsNotNone(is_created_applicable_first)
		self.assertIsNotNone(is_created_applicable_second)
		self.assertEquals(is_created, 1)

	def test_for_apply_to_all_on_update_from_applicable(self):
		''' Update User Permission from some to all applicable Doctypes'''
		user = get_user()
		param = get_params(user, apply_to_all = 1)

		check = add_user_permissions(get_params(user, applicable = ["Chat Room", "Chat Message"]))

		self.assertIsNotNone(check)

		is_created = add_user_permissions(param)
		is_created_apply_to_all = frappe.db.exists("User Permission", get_exists_param(user))
		removed_applicable_first = frappe.db.exists("User Permission", get_exists_param(user, applicable = "Chat Room"))
		removed_applicable_second = frappe.db.exists("User Permission", get_exists_param(user, applicable = "Chat Message"))


		self.assertIsNotNone(is_created_apply_to_all)
		self.assertIsNone(removed_applicable_first)
		self.assertIsNone(removed_applicable_second)
		self.assertEquals(is_created, 1)

def get_user():
	if frappe.db.exists('User', 'test_bulk_creation_update@example.com'):
		return frappe.get_doc('User', 'test_bulk_creation_update@example.com')
	else:
		user = frappe.new_doc('User')
		user.email = 'test_bulk_creation_update@example.com'
		user.first_name = 'Test_Bulk_Creation'
		user.add_roles("System Manager")
		return user

def get_params(user, apply_to_all = None , applicable = None):
	''' Return param to insert '''
	param = {
		"user": user.name,
		"doctype":"User",
		"docname":user.name
	}
	if apply_to_all:
		param.update({"apply_to_all_doctypes": 1})
		param.update({"applicable_doctypes": []})
	if applicable:
		param.update({"apply_to_all_doctypes": 0})
		param.update({"applicable_doctypes": applicable})
	return param

def get_exists_param(user, applicable = None):
	''' param to check existing Document '''
	param = {
		"user": user.name,
		"allow": "User",
		"for_value": user.name,
	}
	if applicable:
		param.update({"applicable_for": applicable})
	else:
		param.update({"apply_to_all_doctypes": 1})
	return param
