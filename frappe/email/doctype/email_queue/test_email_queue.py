# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.email.queue import clear_outbox
from frappe.tests.utils import FrappeTestCase


class TestEmailQueue(FrappeTestCase):
	def test_email_queue_deletion_based_on_modified_date(self):
		old_record = frappe.get_doc(
			{
				"doctype": "Email Queue",
				"sender": "Test <test@example.com>",
				"show_as_cc": "",
				"message": "Test message",
				"status": "Sent",
				"priority": 1,
				"recipients": [
					{
						"recipient": "test_auth@test.com",
					}
				],
			}
		).insert()

		old_record.modified = "2010-01-01 00:00:01"
		old_record.recipients[0].modified = old_record.modified
		old_record.db_update_all()

		new_record = frappe.copy_doc(old_record)
		new_record.insert()

		clear_outbox()

		self.assertFalse(frappe.db.exists("Email Queue", old_record.name))
		self.assertFalse(frappe.db.exists("Email Queue Recipient", {"parent": old_record.name}))

		self.assertTrue(frappe.db.exists("Email Queue", new_record.name))
		self.assertTrue(frappe.db.exists("Email Queue Recipient", {"parent": new_record.name}))
