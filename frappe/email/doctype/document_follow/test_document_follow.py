# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
import unittest
from dataclasses import dataclass
import frappe.desk.form.document_follow as document_follow
from frappe.query_builder import DocType
from frappe.desk.form.utils import add_comment
from frappe.desk.form.document_follow import get_document_followed_by_user
from frappe.desk.like import toggle_like
from frappe.desk.form.assign_to import add
from frappe.share import add as share

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

		Emails = (frappe.qb.from_(EmailQueue)
			.join(EmailQueueRecipient)
			.on(EmailQueueRecipient.parent == EmailQueue.name)
			.where(EmailQueueRecipient.recipient == 'test@docsub.com',)
			.where(EmailQueue.message.like(f'%{event_doc.doctype}%'))
			.where(EmailQueue.message.like(f'%{event_doc.name}%'))
			.where(EmailQueue.message.like('%This is a test description for sending mail%'))
			.select(EmailQueue.message)
			.limit(1)).run()
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
		Emails = (frappe.qb.from_(EmailQueue).join(EmailQueueRecipient)
			.on(EmailQueueRecipient.parent == EmailQueue.name)
			.where(EmailQueueRecipient.recipient == 'test@docsub.com',)
			.where(EmailQueue.message.like(f'%{event_doc.doctype}%'))
			.where(EmailQueue.message.like(f'%{event_doc.name}%'))
			.where(EmailQueue.message.like('%This is a test comment%'))
			.select(EmailQueue.message)
			.limit(1)).run()

		self.assertIsNotNone(Emails)

	def tearDown(self):
		frappe.db.rollback()
		frappe.db.delete('Email Queue')
		frappe.db.delete('Email Queue Recipient')
		frappe.db.delete('Document Follow')

	def test_follow_limit(self):
		user = get_user()
		for _ in range(25):
			event_doc = get_event()
			document_follow.unfollow_document("Event", event_doc.name, user.name)
			doc = document_follow.follow_document("Event", event_doc.name, user.name)
			self.assertEqual(doc.user, user.name)
		self.assertEqual(len(get_document_followed_by_user(user.name)), 20)

	def test_follow_on_create(self):
		user = get_user(DocumentFollowConditions(1))
		frappe.set_user(user.name)
		event_doc = get_event()

		event_doc.description = "This is a test description for sending mail"
		event_doc.save(ignore_version=False)

		DocumentFollow = DocType('Document Follow')
		document_follow = (frappe.qb.from_(DocumentFollow)
			.where(DocumentFollow.ref_doctype == 'Event')
			.where(DocumentFollow.ref_docname == event_doc.name)
			.where(DocumentFollow.user == user.name)
			.select(DocumentFollow.name)).run()

		self.assertIsNotNone(document_follow)

	def test_do_not_follow_on_create(self):
		user = get_user()
		frappe.set_user(user.name)
		event_doc = get_event()
		DocumentFollow = DocType('Document Follow')
		document_follow = (frappe.qb.from_(DocumentFollow)
			.where(DocumentFollow.ref_doctype == 'Event')
			.where(DocumentFollow.ref_docname == event_doc.name)
			.where(DocumentFollow.user == user.name)
			.select(DocumentFollow.name)).run()
		self.assertFalse(document_follow)

	def test_do_not_follow_on_update(self):
		user = get_user()
		frappe.set_user(user.name)
		event_doc = get_event()
		event_doc.description = "This is a test description for sending mail"
		event_doc.save(ignore_version=False)
		DocumentFollow = DocType('Document Follow')
		document_follow = (frappe.qb.from_(DocumentFollow)
			.where(DocumentFollow.ref_doctype == 'Event')
			.where(DocumentFollow.ref_docname == event_doc.name)
			.where(DocumentFollow.user == user.name)
			.select(DocumentFollow.name)).run()
		self.assertFalse(document_follow)

	def test_follow_on_comment(self):
		frappe.db.delete('Document Follow')
		user = get_user(DocumentFollowConditions(0, 1))
		frappe.set_user(user.name)
		event_doc = get_event()

		add_comment(event_doc.doctype, event_doc.name, "This is a test comment", 'Administrator@example.com', 'Bosh')

		DocumentFollow = DocType('Document Follow')
		document_follow = (frappe.qb.from_(DocumentFollow)
			.where(DocumentFollow.ref_doctype == 'Event')
			.where(DocumentFollow.ref_docname == event_doc.name)
			.where(DocumentFollow.user == user.name)
			.select(DocumentFollow.name)).run()
		self.assertTrue(document_follow)

	def test_do_not_follow_on_comment(self):
		frappe.db.delete('Document Follow')
		user = get_user()
		frappe.set_user(user.name)
		event_doc = get_event()
		add_comment(event_doc.doctype, event_doc.name, "This is a test comment", 'Administrator@example.com', 'Bosh')
		DocumentFollow = DocType('Document Follow')
		document_follow = (frappe.qb.from_(DocumentFollow)
			.where(DocumentFollow.ref_doctype == 'Event')
			.where(DocumentFollow.ref_docname == event_doc.name)
			.where(DocumentFollow.user == user.name)
			.select(DocumentFollow.name)).run()
		self.assertFalse(document_follow)

	def test_follow_on_like(self):
		frappe.db.delete('Document Follow')
		user = get_user(DocumentFollowConditions(0, 0, 1))
		frappe.set_user(user.name)
		event_doc = get_event()

		toggle_like(event_doc.doctype, event_doc.name, add="Yes")

		DocumentFollow = DocType('Document Follow')
		document_follow = (frappe.qb.from_(DocumentFollow)
			.where(DocumentFollow.ref_doctype == 'Event')
			.where(DocumentFollow.ref_docname == event_doc.name)
			.where(DocumentFollow.user == user.name)
			.select(DocumentFollow.name)).run()
		self.assertTrue(document_follow)

	def test_do_not_follow_on_like(self):
		frappe.db.delete('Document Follow')
		user = get_user()
		frappe.set_user(user.name)
		event_doc = get_event()

		toggle_like(event_doc.doctype, event_doc.name)

		DocumentFollow = DocType('Document Follow')
		document_follow = (frappe.qb.from_(DocumentFollow)
			.where(DocumentFollow.ref_doctype == 'Event')
			.where(DocumentFollow.ref_docname == event_doc.name)
			.where(DocumentFollow.user == user.name)
			.select(DocumentFollow.name)).run()
		self.assertFalse(document_follow)

	def test_follow_on_assign(self):
		frappe.db.delete('Document Follow')
		user = get_user(DocumentFollowConditions(0, 0, 0, 1))
		event_doc = get_event()
		add({
			'assign_to': [user.name],
			'doctype': event_doc.doctype,
			'name': event_doc.name
		})
		DocumentFollow = DocType('Document Follow')
		document_follow = (frappe.qb.from_(DocumentFollow)
			.where(DocumentFollow.ref_doctype == 'Event')
			.where(DocumentFollow.ref_docname == event_doc.name)
			.where(DocumentFollow.user == user.name)
			.select(DocumentFollow.name)).run()
		self.assertTrue(document_follow)

	def test_do_not_follow_on_assign(self):
		frappe.db.delete('Document Follow')
		user = get_user()
		frappe.set_user(user.name)
		event_doc = get_event()

		add({
			'assign_to': [user.name],
			'doctype': event_doc.doctype,
			'name': event_doc.name
		})

		DocumentFollow = DocType('Document Follow')
		document_follow = (frappe.qb.from_(DocumentFollow)
			.where(DocumentFollow.ref_doctype == 'Event')
			.where(DocumentFollow.ref_docname == event_doc.name)
			.where(DocumentFollow.user == user.name)
			.select(DocumentFollow.name)).run()
		self.assertFalse(document_follow)

	def test_follow_on_share(self):
		frappe.db.delete('Document Follow')
		user = get_user(DocumentFollowConditions(0, 0, 0, 0, 1))
		event_doc = get_event()
		share(
			user= user.name,
			doctype= event_doc.doctype,
			name= event_doc.name
		)
		DocumentFollow = DocType('Document Follow')
		document_follow = (frappe.qb.from_(DocumentFollow)
			.where(DocumentFollow.ref_doctype == 'Event')
			.where(DocumentFollow.ref_docname == event_doc.name)
			.where(DocumentFollow.user == user.name)
			.select(DocumentFollow.name)).run()
		self.assertTrue(document_follow)

	def test_do_not_follow_on_share(self):
		frappe.db.delete('Document Follow')
		user = get_user()
		event_doc = get_event()

		share(
			user = user.name,
			doctype = event_doc.doctype,
			name = event_doc.name
		)

		DocumentFollow = DocType('Document Follow')
		document_follow = (frappe.qb.from_(DocumentFollow)
			.where(DocumentFollow.ref_doctype == 'Event')
			.where(DocumentFollow.ref_docname == event_doc.name)
			.where(DocumentFollow.user == user.name)
			.select(DocumentFollow.name)).run()
		self.assertFalse(document_follow)

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

def get_user(document_follow=None):
	frappe.set_user("Administrator")
	if frappe.db.exists('User', 'test@docsub.com'):
		doc = frappe.delete_doc('User', 'test@docsub.com')
	doc = frappe.new_doc("User")
	doc.email = "test@docsub.com"
	doc.first_name = "Test"
	doc.last_name = "User"
	doc.send_welcome_email = 0
	doc.document_follow_notify = 1
	doc.document_follow_frequency = "Hourly"
	doc.__dict__.update(document_follow.__dict__ if document_follow else {})
	doc.insert()
	doc.add_roles('System Manager')
	return doc


@dataclass
class DocumentFollowConditions:
	follow_created_documents: int = 0
	follow_commented_documents: int = 0
	follow_liked_documents: int = 0
	follow_assigned_documents: int = 0
	follow_shared_documents: int = 0
