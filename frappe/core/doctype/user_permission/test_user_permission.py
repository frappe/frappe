# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals
from frappe.core.doctype.user_permission.user_permission import add_user_permissions

import frappe
import unittest

class TestUserPermission(unittest.TestCase):
	def test_apply_to_all(self):
		user = get_user()
		created = add_user_permissions({
			"user": user.name,
			"doctype":"User",
			"docname":user.name ,
			"apply_to_all_doctypes":1})
		self.assertEquals(created, 1)

	def test_for_applicables_on_update_from_apply_to_all(self):
		user = get_user()
		create = add_user_permissions({
			"user": user.name,
			"doctype":"User",
			"docname":user.name ,
			"apply_to_all_doctypes":0,
			"applicable_doctypes":["Chat Room","Chat Message"]})
		frappe.db.commit()

		removed_apply_to_all = frappe.db.exists("User Permission", {
			"user": user.name,
			"allow": "User",
			"for_value": user.name,
			"apply_to_all_doctypes": 1})
		created_applicable_first = frappe.db.exists("User Permission", {
			"user": user.name,
			"allow": "User",
			"for_value": user.name,
			"apply_to_all_doctypes": 0,
			"applicable_for": "Chat Room"})
		created_applicable_second = frappe.db.exists("User Permission", {
			"user": user.name,
			"allow": "User",
			"for_value": user.name,
			"apply_to_all_doctypes": 0,
			"applicable_for": "Chat Message"})

		self.assertIsNone(removed_apply_to_all)
		self.assertIsNotNone(created_applicable_first)
		self.assertIsNotNone(created_applicable_second)
		self.assertEquals(create, 1)

	def test_for_apply_to_all_on_update_from_applicables(self):
		user = get_user()
		created = add_user_permissions({
			"user": user.name,
			"doctype":"User",
			"docname":user.name ,
			"apply_to_all_doctypes":1})
		created_apply_to_all = frappe.db.exists("User Permission", {
			"user": user.name,
			"allow": "User",
			"for_value": user.name,
			"apply_to_all_doctypes": 1})
		removed_applicable_first = frappe.db.exists("User Permission", {
			"user": user.name,
			"allow": "User",
			"for_value": user.name,
			"apply_to_all_doctypes": 0,
			"applicable_for": "Chat Room"})
		removed_applicable_second = frappe.db.exists("User Permission", {
			"user": user.name, "allow": "User",
			"for_value": user.name,
			"apply_to_all_doctypes": 0,
			"applicable_for": "Chat Message"})


		self.assertIsNotNone(created_apply_to_all)
		self.assertIsNone(removed_applicable_first)
		self.assertIsNone(removed_applicable_second)
		self.assertEquals(created, 1)

def get_user():
	if frappe.db.exists('User', 'test_bulk_creation_update@example.com'):
		return frappe.get_doc('User', 'test_bulk_creation_update@example.com')
	else:
		user = frappe.new_doc('User')
		user.email = 'test_bulk_creation_update@example.com'
		user.first_name = 'Test_Bulk_Creation'
		user.add_roles("System Manager")
		return user


