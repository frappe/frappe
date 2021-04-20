# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals
from frappe.core.doctype.user_permission.user_permission import add_user_permissions, remove_applicable
from frappe.permissions import has_user_permission
from frappe.core.doctype.doctype.test_doctype import new_doctype

import frappe
import unittest

class TestUserPermission(unittest.TestCase):
	def setUp(self):
		frappe.db.sql("""DELETE FROM `tabUser Permission`
			WHERE `user` in (
				'test_bulk_creation_update@example.com',
				'test_user_perm1@example.com',
				'nested_doc_user@example.com')""")
		frappe.delete_doc_if_exists("DocType", "Person")
		frappe.db.sql_ddl("DROP TABLE IF EXISTS `tabPerson`")
		frappe.delete_doc_if_exists("DocType", "Doc A")
		frappe.db.sql_ddl("DROP TABLE IF EXISTS `tabDoc A`")

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
				frappe.get_doc({'doctype': 'Blog Category', 'title': category}).insert()

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

	def test_user_perm_for_nested_doctype(self):
		"""Test if descendants' visibility is controlled for a nested DocType."""
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		user = create_user("nested_doc_user@example.com", "Blogger")
		if not frappe.db.exists("DocType", "Person"):
			doc = new_doctype("Person",
				fields=[
					{
						"label": "Person Name",
						"fieldname": "person_name",
						"fieldtype": "Data"
					}
				], unique=0)
			doc.is_tree = 1
			doc.insert()

		parent_record = frappe.get_doc(
			{"doctype": "Person", "person_name": "Parent", "is_group": 1}
		).insert()

		child_record = frappe.get_doc(
			{"doctype": "Person", "person_name": "Child", "is_group": 0, "parent_person": parent_record.name}
		).insert()

		add_user_permissions(get_params(user, "Person", parent_record.name))

		# check if adding perm on a group record, makes child record visible
		self.assertTrue(has_user_permission(frappe.get_doc("Person", parent_record.name), user.name))
		self.assertTrue(has_user_permission(frappe.get_doc("Person", child_record.name), user.name))

		frappe.db.set_value("User Permission", {"allow": "Person", "for_value": parent_record.name}, "hide_descendants", 1)
		frappe.cache().delete_value("user_permissions")

		# check if adding perm on a group record with hide_descendants enabled,
		# hides child records
		self.assertTrue(has_user_permission(frappe.get_doc("Person", parent_record.name), user.name))
		self.assertFalse(has_user_permission(frappe.get_doc("Person", child_record.name), user.name))

	def test_user_perm_on_new_doc_with_field_default(self):
		"""Test User Perm impact on frappe.new_doc. with *field* default value"""
		frappe.set_user('Administrator')
		user = create_user("new_doc_test@example.com", "Blogger")

		# make a doctype "Doc A" with 'doctype' link field and default value ToDo
		if not frappe.db.exists("DocType", "Doc A"):
			doc = new_doctype("Doc A",
				fields=[
					{
						"label": "DocType",
						"fieldname": "doc",
						"fieldtype": "Link",
						"options": "DocType",
						"default": "ToDo"
					}
				], unique=0)
			doc.insert()

		# make User Perm on DocType 'ToDo' in Assignment Rule (unrelated doctype)
		add_user_permissions(get_params(user, "DocType", "ToDo", applicable=["Assignment Rule"]))
		frappe.set_user("new_doc_test@example.com")

		new_doc = frappe.new_doc("Doc A")

		# User perm is created on ToDo but for doctype Assignment Rule only
		# it should not have impact on Doc A
		self.assertEquals(new_doc.doc, "ToDo")

		frappe.set_user('Administrator')
		remove_applicable(["Assignment Rule"], "new_doc_test@example.com", "DocType", "ToDo")

	def test_user_perm_on_new_doc_with_user_default(self):
		"""Test User Perm impact on frappe.new_doc. with *user* default value"""
		from frappe.core.doctype.session_default_settings.session_default_settings import (clear_session_defaults,
			set_session_default_values)

		frappe.set_user('Administrator')
		user = create_user("user_default_test@example.com", "Blogger")

		# make a doctype "Doc A" with 'doctype' link field
		if not frappe.db.exists("DocType", "Doc A"):
			doc = new_doctype("Doc A",
				fields=[
					{
						"label": "DocType",
						"fieldname": "doc",
						"fieldtype": "Link",
						"options": "DocType",
					}
				], unique=0)
			doc.insert()

		# create a 'DocType' session default field
		if not frappe.db.exists("Session Default", {"ref_doctype": "DocType"}):
			settings = frappe.get_single('Session Default Settings')
			settings.append("session_defaults", {
				"ref_doctype": "DocType"
			})
			settings.save()

		# make User Perm on DocType 'ToDo' in Assignment Rule (unrelated doctype)
		add_user_permissions(get_params(user, "DocType", "ToDo", applicable=["Assignment Rule"]))

		# User default Doctype value is ToDo via Session Defaults
		frappe.set_user("user_default_test@example.com")
		set_session_default_values({"doc": "ToDo"})

		new_doc = frappe.new_doc("Doc A")

		# User perm is created on ToDo but for doctype Assignment Rule only
		# it should not have impact on Doc A
		self.assertEquals(new_doc.doc, "ToDo")

		frappe.set_user('Administrator')
		clear_session_defaults()
		remove_applicable(["Assignment Rule"], "user_default_test@example.com", "DocType", "ToDo")

def create_user(email, *roles):
	''' create user with role system manager '''
	if frappe.db.exists('User', email):
		return frappe.get_doc('User', email)

	user = frappe.new_doc('User')
	user.email = email
	user.first_name = email.split("@")[0]

	if not roles:
		roles = ('System Manager',)

	user.add_roles(*roles)
	return user

def get_params(user, doctype, docname, is_default=0, hide_descendants=0, applicable=None):
	''' Return param to insert '''
	param = {
		"user": user.name,
		"doctype":doctype,
		"docname":docname,
		"is_default": is_default,
		"apply_to_all_doctypes": 1,
		"applicable_doctypes": [],
		"hide_descendants": hide_descendants
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
