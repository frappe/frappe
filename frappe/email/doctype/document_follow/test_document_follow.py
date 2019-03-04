# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import frappe.desk.form.document_follow as document_follow

class TestDocumentFollow(unittest.TestCase):

	def test_add_subscription_and_send_mail(self):
		user = get_user()
		event_doc = get_event()

		event_doc.description = "This is a test description for sending mail"
		event_doc.save()

		doc = document_follow.follow_document("Event", event_doc.name , user.name, force=True)
		self.assertEquals(doc.user, user.name)

		document_follow.send_hourly_updates()

		email_queue_entry_name = frappe.get_all("Email Queue", limit=1)[0].name
		email_queue_entry_doc = frappe.get_doc("Email Queue", email_queue_entry_name)

		self.assertEquals((email_queue_entry_doc.recipients[0].recipient), user.name)

		self.assertIn(event_doc.doctype, email_queue_entry_doc.message)
		self.assertIn(event_doc.name, email_queue_entry_doc.message)


	def tearDown(self):
		frappe.db.rollback()

def get_event():
	doc = frappe.get_doc({
		'doctype': 'Event',
		'subject': "_Test_Doc_Follow",
		'doc.starts_on':  frappe.utils.now(),
		'doc.ends_on': frappe.utils.add_days(frappe.utils.now(),5),
		'doc.description': "Hello"
	})
	doc.insert()
	return doc

def get_user():
		doc = frappe.new_doc("User")
		doc.email = "test@docsub.com"
		doc.first_name = "Test"
		doc.last_name = "User"
		doc.send_welcome_email = 0
		doc.document_follow_notify = 1
		doc.document_follow_frequency = "Hourly"
		doc.insert()
		return doc