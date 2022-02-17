# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from queue import Queue
import frappe
import unittest
import frappe.desk.form.document_follow as document_follow
from frappe.query_builder import DocType

class TestDocumentFollow(unittest.TestCase):
	def test_document_follow(self):
		user = get_user()
		event_doc = get_event()

		event_doc.description = "This is a test description for sending mail"
		event_doc.save(ignore_version=False)

		document_follow.unfollow_document("Event", event_doc.name, user.name)
		doc = document_follow.follow_document("Event", event_doc.name, user.name)
		self.assertEqual(doc.user, user.name)

		document_follow.send_hourly_updates()

		EmailQueue = DocType('Email Queue')
		EmailQueueRecipient = DocType('Email Queue Recipient')


		Emails = frappe.qb.from_(EmailQueue).join(EmailQueueRecipient).on(
				EmailQueueRecipient.parent == EmailQueue.name
			).where(
				EmailQueueRecipient.recipient == 'test@docsub.com',
			).where(
				EmailQueueRecipient.recipient.like(f'%{event_doc.doctype}%')
			).where(
				EmailQueueRecipient.recipient.like(f'%{event_doc.name}%')
			).select(
				EmailQueue.message
			).limit(1).run()

		self.assertIsNotNone(Emails)


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
	if frappe.db.exists('User', 'test@docsub.com'):
		doc = frappe.get_doc('User', 'test@docsub.com')
	else:
		doc = frappe.new_doc("User")
		doc.email = "test@docsub.com"
		doc.first_name = "Test"
		doc.last_name = "User"
		doc.send_welcome_email = 0
		doc.document_follow_notify = 1
		doc.document_follow_frequency = "Hourly"
		doc.insert()
	return doc