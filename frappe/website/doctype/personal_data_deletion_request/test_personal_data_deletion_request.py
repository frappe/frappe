# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from frappe.website.doctype.personal_data_deletion_request.personal_data_deletion_request import (
	remove_unverified_record,
)
from frappe.website.doctype.personal_data_download_request.test_personal_data_download_request import (
	create_user_if_not_exists,
)
from datetime import datetime, timedelta


class TestPersonalDataDeletionRequest(unittest.TestCase):
	def setUp(self):
		create_user_if_not_exists(email="test_delete@example.com")
		self.delete_request = frappe.get_doc(
			{"doctype": "Personal Data Deletion Request", "email": "test_delete@example.com"}
		)
		self.delete_request.save(ignore_permissions=True)

	def test_delete_request(self):
		email_queue = frappe.get_all("Email Queue", fields=["*"], order_by="creation desc", limit=1)

		self.assertEqual(self.delete_request.status, "Pending Verification")
		self.assertTrue("Subject: Confirm Deletion of Data" in email_queue[0].message)

	def test_anonymized_data(self):
		self.delete_request.status = "Pending Approval"
		self.delete_request.save()
		self.delete_request.trigger_data_deletion()
		self.delete_request.reload()

		deleted_user = frappe.get_all(
			"User",
			filters={"name": self.delete_request.name},
			fields=["first_name", "last_name", "phone", "birth_date"],
		)[0]

		self.assertEqual(deleted_user.first_name, self.delete_request.anonymization_value_map["Data"])
		self.assertEqual(deleted_user.last_name, self.delete_request.anonymization_value_map["Data"])
		self.assertEqual(deleted_user.phone, self.delete_request.anonymization_value_map["Phone"])
		self.assertEqual(
			deleted_user.birth_date,
			datetime.strptime(self.delete_request.anonymization_value_map["Date"], "%Y-%m-%d").date()
		)
		self.assertEqual(self.delete_request.status, "Deleted")

	def test_unverified_record_removal(self):
		date_time_obj = datetime.strptime(
			self.delete_request.creation, "%Y-%m-%d %H:%M:%S.%f"
		)
		date_time_obj += timedelta(days=-7)
		self.delete_request.creation = date_time_obj
		self.status = "Pending Verification"
		self.delete_request.save()
		remove_unverified_record()
		self.assertFalse(
			frappe.db.exists("Personal Data Deletion Request", self.delete_request.name)
		)
