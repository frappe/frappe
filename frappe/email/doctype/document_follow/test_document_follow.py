# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import frappe.desk.form.document_follow as document_follow
from pprint import pprint

class TestDocumentFollow(unittest.TestCase):

	def test_add_subscription_and_send_mail(self):
		print("test_add_subscription")
		user = get_user()
		event_doc = get_event()
		event_doc.description = "This is a test description for sending mail"
		event_doc.save()
		doc = document_follow.follow_document("Event", event_doc.name , user.name)

		document_follow.send_hourly_updates()
		email_queue_entry = frappe.get_doc("Email Queue", {
			'reference_doctype': 'Event',
			'reference_name': event_doc.name
		})
		print(event_doc.name, email_queue_entry.reference_name)
		self.assertEquals(doc.user, user.name)
		self.assertEquals(email_queue_entry.reference_doctype, 'Event')
		self.assertEquals(email_queue_entry.reference_name, event_doc.name)
		self.assertEquals((email_queue_entry.recipients[0].recipient), user.name)

	def tearDown(self):
		print("Rolling Back")
		frappe.db.rollback()

def get_event():
	doc = frappe.new_doc("Event")
	doc.subject = "_Test_Doc_Follow"
	doc.starts_on = frappe.utils.now()
	doc.ends_on = frappe.utils.add_days(frappe.utils.now(),5)
	doc.description = "Hello"
	doc.insert()
	return doc

def get_user():
		print("inside if")
		doc = frappe.new_doc("User")
		doc.email = "test@docsub.com"
		doc.first_name = "Test"
		doc.last_name = "User"
		doc.send_welcome_email = 0
		doc.document_follow_notify = 1
		doc.document_follow_frequency = "Hourly"
		doc.insert()
		return doc