# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

# test_records = frappe.get_test_records('Email Group Member')

class TestEmailGroupMember(unittest.TestCase):
	def setUp(self):
		frappe.delete_doc_if_exists("Email Group", "_Test Email Group")
		frappe.get_doc({
			"doctype": "Email Group",
			"title": "_Test Email Group",
			"total_subscribers": 0
		}).insert(ignore_permissions=True)

		frappe.db.sql("delete from `tabEmail Group Member` where email_group = '_Test Email Group'")
		for email in ["test1@example.com", "test2@example.com"]:
			frappe.get_doc({
				"doctype": "Email Group Member",
				"email_group": "_Test Email Group",
				"email": email,
				"unsubscribed": 0
			}).insert(ignore_permissions=True)

	def test_total_subscribers(self):
		email_group_mem = frappe.db.get_value("Email Group Member", {"email": "test1@example.com"}, "name")
		frappe.delete_doc('Email Group Member', email_group_mem)
		total_subscribers = frappe.db.get_value("Email Group", "_Test Email Group", "total_subscribers")
		self.assertEquals(total_subscribers, 1)
