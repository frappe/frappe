# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from frappe.website.doctype.personal_data_deletion_request.personal_data_deletion_request import PersonalDataDeletionRequest, remove_unverified_record
from frappe.website.doctype.personal_data_download_request.test_personal_data_download_request import create_user_if_not_exists
from datetime import datetime, timedelta, date

class TestPersonalDataDeletionRequest(unittest.TestCase):
	def setUp(self):
		create_user_if_not_exists(email='test_delete@example.com')
		self.delete_request = frappe.get_doc({
			'doctype':'Personal Data Deletion Request',
			'email':'test_delete@example.com'
		})
		self.delete_request.save(ignore_permissions=True)

	def test_delete_request(self):
		self.assertEqual(self.delete_request.status, 'Pending Verification')

		email_queue = frappe.db.sql("""SELECT *
			FROM `tabEmail Queue`
			ORDER BY `creation` DESC""", as_dict=True)
		self.assertTrue("Subject: Confirm Deletion of Data" in email_queue[0].message)

	def test_anonymized_data(self):
		self.delete_request.status = 'Pending Approval'
		self.delete_request.save()
		PersonalDataDeletionRequest.anonymize_data(self.delete_request)
		deleted_user = frappe.get_all('User',
			filters = {'name': self.delete_request.name},
			fields = ['first_name', 'last_name', 'phone', 'birth_date'])
		self.assertEqual(len(deleted_user), 1)

		expected_data = [{
			'first_name': 'first_name',
  			'last_name': 'last_name',
  			'phone': 'phone',
			'birth_date': date(1111,1,1),
		}]
		self.assertEqual(expected_data, deleted_user)
		self.assertEqual(self.delete_request.status, 'Deleted')

	def test_unverified_record_removal(self):
		date_time_obj = datetime.strptime(self.delete_request.creation, '%Y-%m-%d %H:%M:%S.%f')
		date_time_obj += timedelta(days=-7)
		self.delete_request.creation = date_time_obj
		self.status = 'Pending Verification'
		self.delete_request.save()
		remove_unverified_record()
		self.assertFalse(frappe.db.exists("Personal Data Deletion Request", self.delete_request.name))