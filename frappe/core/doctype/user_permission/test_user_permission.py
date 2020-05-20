# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals
from frappe.core.doctype.user_permission.user_permission import add_user_permissions

import frappe
import unittest

class TestUserPermission(unittest.TestCase):
	def setUp(self):
		frappe.db.sql("""DELETE FROM `tabUser Permission`
			WHERE `user` in ('test_bulk_creation_update@example.com', 'test_user_perm1@example.com')""")

	def test_default_user_permission_validation(self):
		user = create_user('test_default_permission@example.com')
		param = get_params(user, 'User', user.name, is_default=1)
		add_user_permissions(param)
		#create a duplicate entry with default
		perm_user = create_user('test_user_perm@example.com')
		param = get_params(user, 'User', perm_user.name, is_default=1)
		self.assertRaises(frappe.ValidationError, add_user_permissions, param)

	def test_default_user_permission(self):
		frappe.set_user('Administrator')
		user = create_user('test_user_perm1@example.com', 'Website Manager')
		for category in ['general', 'public']:
			if not frappe.db.exists('Blog Category', category):
				frappe.get_doc({'doctype': 'Blog Category',
					'category_name': category, 'title': category}).insert()

		param = get_params(user, 'Blog Category', 'general', is_default=1)
		add_user_permissions(param)

		param = get_params(user, 'Blog Category', 'public')
		add_user_permissions(param)

		frappe.set_user('test_user_perm1@example.com')
		doc = frappe.new_doc("Blog Post")

		self.assertEquals(doc.blog_category, 'general')
		frappe.set_user('Administrator')

	def test_apply_to_all(self):
		''' Create User permission for User having access to all applicable Doctypes'''
		user = create_user('test_bulk_creation_update@example.com')
		param = get_params(user, 'User', user.name)
		is_created = add_user_permissions(param)
		self.assertEquals(is_created, 1)

	def test_for_apply_to_all_on_update_from_apply_all(self):
		user = create_user('test_bulk_creation_update@example.com')
		param = get_params(user, 'User', user.name)

		# Initially create User Permission document with apply_to_all checked
		is_created = add_user_permissions(param)

		self.assertEquals(is_created, 1)
		is_created = add_user_permissions(param)

		# User Permission should not be changed
		self.assertEquals(is_created, 0)

	def test_for_applicable_on_update_from_apply_to_all(self):
		''' Update User Permission from all to some applicable Doctypes'''
		user = create_user('test_bulk_creation_update@example.com')
		param = get_params(user,'User', user.name, applicable = ["Chat Room", "Chat Message"])

		# Initially create User Permission document with apply_to_all checked
		is_created = add_user_permissions(get_params(user, 'User', user.name))

		self.assertEquals(is_created, 1)

		is_created = add_user_permissions(param)
		frappe.db.commit()

		removed_apply_to_all = frappe.db.exists("User Permission", get_exists_param(user))
		is_created_applicable_first = frappe.db.exists("User Permission", get_exists_param(user, applicable = "Chat Room"))
		is_created_applicable_second = frappe.db.exists("User Permission", get_exists_param(user, applicable = "Chat Message"))

		# Check that apply_to_all is removed
		self.assertIsNone(removed_apply_to_all)

		# Check that User Permissions for applicable is created
		self.assertIsNotNone(is_created_applicable_first)
		self.assertIsNotNone(is_created_applicable_second)
		self.assertEquals(is_created, 1)

	def test_for_apply_to_all_on_update_from_applicable(self):
		''' Update User Permission from some to all applicable Doctypes'''
		user = create_user('test_bulk_creation_update@example.com')
		param = get_params(user, 'User', user.name)

		# create User permissions that with applicable
		is_created = add_user_permissions(get_params(user, 'User', user.name, applicable = ["Chat Room", "Chat Message"]))

		self.assertEquals(is_created, 1)

		is_created = add_user_permissions(param)
		is_created_apply_to_all = frappe.db.exists("User Permission", get_exists_param(user))
		removed_applicable_first = frappe.db.exists("User Permission", get_exists_param(user, applicable = "Chat Room"))
		removed_applicable_second = frappe.db.exists("User Permission", get_exists_param(user, applicable = "Chat Message"))

		# To check that a User permission with apply_to_all exists
		self.assertIsNotNone(is_created_apply_to_all)

		# Check that all User Permission with applicable is removed
		self.assertIsNone(removed_applicable_first)
		self.assertIsNone(removed_applicable_second)
		self.assertEquals(is_created, 1)

def create_user(email, role="System Manager"):
	''' create user with role system manager '''
	if frappe.db.exists('User', email):
		return frappe.get_doc('User', email)
	else:
		user = frappe.new_doc('User')
		user.email = email
		user.first_name = email.split("@")[0]
		user.add_roles(role)
		return user

def get_params(user, doctype, docname, is_default=0, applicable=None):
	''' Return param to insert '''
	param = {
		"user": user.name,
		"doctype":doctype,
		"docname":docname,
		"is_default": is_default,
		"apply_to_all_doctypes": 1,
		"applicable_doctypes": []
	}
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
