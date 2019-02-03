# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from erpnext.shopping_cart.test_shopping_cart import create_user_if_not_exists
from frappe.website.doctype.personal_data_delete_request.personal_data_delete_request import PersonalDataDeleteRequest

class TestPersonalDataDeleteRequest(unittest.TestCase):
	def setUp(self):
		create_user_if_not_exists('test_delete@example.com')
		frappe.set_user('test_delete@example.com')
		self.delete_request = frappe.get_doc({'doctype':'Personal Data Delete Request', 'email':'test_delete@example.com'})
		self.delete_request.save(ignore_permissions=True)

	def test_delete_request(self):
		self.assertTrue(self.delete_request.status, 'Verification Pending')

		email_queue = frappe.db.sql("""select * from `tabEmail Queue`""", as_dict=True)
		self.assertTrue("Subject: ERPNext: Confirm Deletion of Data" in email_queue[0].message)

		frappe.db.sql("delete from `tabEmail Queue`")

	def test_anonymized_data(self):
		PersonalDataDeleteRequest.anonymize_data(self.delete_request)
		print(self.delete_request.name)
		deleted_user = frappe.get_all('Contact', {'email_id': self.delete_request.name}, ['*'])
		self.assertTrue(len(deleted_user), 1)
