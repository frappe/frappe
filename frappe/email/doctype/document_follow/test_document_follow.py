# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
import unittest
import frappe.desk.form.document_follow as document_follow
from frappe.query_builder import DocType
from frappe.desk.form.utils import add_comment

class TestDocumentFollow(unittest.TestCase):
	def test_document_follow_version(self):
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
				EmailQueue.message.like(f'%{event_doc.doctype}%')
			).where(
				EmailQueue.message.like(f'%{event_doc.name}%')
			).where(
				EmailQueue.message.like('%This is a test description for sending mail%')
			).select(
				EmailQueue.message
			).limit(1).run()
		self.assertIsNotNone(Emails)


	def test_document_follow_comment(self):
		user = get_user()
		event_doc = get_event()

		add_comment(event_doc.doctype, event_doc.name,  "This is a test comment", 'Administrator@example.com', 'Bosh')

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
				EmailQueue.message.like(f'%{event_doc.doctype}%')
			).where(
				EmailQueue.message.like(f'%{event_doc.name}%')
			).where(
				EmailQueue.message.like('%This is a test comment%')
			).select(
				EmailQueue.message
			).limit(1).run()

		self.assertIsNotNone(Emails)

	def tearDown(self):
		frappe.db.rollback()
		frappe.db.sql("delete from `tabEmail Queue`")
		frappe.db.sql("delete from `tabEmail Queue Recipient`")

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
