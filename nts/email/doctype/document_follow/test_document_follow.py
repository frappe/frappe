# Copyright (c) 2019, nts Technologies and Contributors
# License: MIT. See LICENSE
from dataclasses import dataclass

import nts
import nts.desk.form.document_follow as document_follow
from nts.desk.form.assign_to import add
from nts.desk.form.document_follow import get_document_followed_by_user
from nts.desk.form.utils import add_comment
from nts.desk.like import toggle_like
from nts.query_builder import DocType
from nts.query_builder.functions import Cast_
from nts.share import add as share
from nts.tests.utils import ntsTestCase


class TestDocumentFollow(ntsTestCase):
	def test_document_follow_version(self):
		user = get_user()
		event_doc = get_event()

		event_doc.description = "This is a test description for sending mail"
		event_doc.save(ignore_version=False)

		document_follow.unfollow_document("Event", event_doc.name, user.name)
		doc = document_follow.follow_document("Event", event_doc.name, user.name)
		self.assertEqual(doc.user, user.name)

		document_follow.send_hourly_updates()
		emails = get_emails(event_doc, "%This is a test description for sending mail%")
		self.assertIsNotNone(emails)

	def test_document_follow_comment(self):
		user = get_user()
		event_doc = get_event()

		add_comment(
			event_doc.doctype, event_doc.name, "This is a test comment", "Administrator@example.com", "Bosh"
		)

		document_follow.unfollow_document("Event", event_doc.name, user.name)
		doc = document_follow.follow_document("Event", event_doc.name, user.name)
		self.assertEqual(doc.user, user.name)

		document_follow.send_hourly_updates()
		emails = get_emails(event_doc, "%This is a test comment%")
		self.assertIsNotNone(emails)

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
		nts.set_user(user.name)
		event = get_event()

		event.description = "This is a test description for sending mail"
		event.save(ignore_version=False)

		documents_followed = get_events_followed_by_user(event.name, user.name)
		self.assertTrue(documents_followed)

	def test_do_not_follow_on_create(self):
		user = get_user()
		nts.set_user(user.name)

		event = get_event()

		documents_followed = get_events_followed_by_user(event.name, user.name)
		self.assertFalse(documents_followed)

	def test_do_not_follow_on_update(self):
		user = get_user()
		nts.set_user(user.name)
		event = get_event()

		event.description = "This is a test description for sending mail"
		event.save(ignore_version=False)

		documents_followed = get_events_followed_by_user(event.name, user.name)
		self.assertFalse(documents_followed)

	def test_follow_on_comment(self):
		user = get_user(DocumentFollowConditions(0, 1))
		nts.set_user(user.name)
		event = get_event()

		add_comment(event.doctype, event.name, "This is a test comment", "Administrator@example.com", "Bosh")

		documents_followed = get_events_followed_by_user(event.name, user.name)
		self.assertTrue(documents_followed)

	def test_do_not_follow_on_comment(self):
		user = get_user()
		nts.set_user(user.name)
		event = get_event()

		add_comment(event.doctype, event.name, "This is a test comment", "Administrator@example.com", "Bosh")

		documents_followed = get_events_followed_by_user(event.name, user.name)
		self.assertFalse(documents_followed)

	def test_follow_on_like(self):
		user = get_user(DocumentFollowConditions(0, 0, 1))
		nts.set_user(user.name)
		event = get_event()

		toggle_like(event.doctype, event.name, add="Yes")

		documents_followed = get_events_followed_by_user(event.name, user.name)
		self.assertTrue(documents_followed)

	def test_do_not_follow_on_like(self):
		user = get_user()
		nts.set_user(user.name)
		event = get_event()

		toggle_like(event.doctype, event.name)

		documents_followed = get_events_followed_by_user(event.name, user.name)
		self.assertFalse(documents_followed)

	def test_follow_on_assign(self):
		user = get_user(DocumentFollowConditions(0, 0, 0, 1))
		event = get_event()

		add({"assign_to": [user.name], "doctype": event.doctype, "name": event.name})

		documents_followed = get_events_followed_by_user(event.name, user.name)
		self.assertTrue(documents_followed)

	def test_do_not_follow_on_assign(self):
		user = get_user()
		nts.set_user(user.name)
		event = get_event()

		add({"assign_to": [user.name], "doctype": event.doctype, "name": event.name})

		documents_followed = get_events_followed_by_user(event.name, user.name)
		self.assertFalse(documents_followed)

	def test_follow_on_share(self):
		user = get_user(DocumentFollowConditions(0, 0, 0, 0, 1))
		event = get_event()

		share(user=user.name, doctype=event.doctype, name=event.name)

		documents_followed = get_events_followed_by_user(event.name, user.name)
		self.assertTrue(documents_followed)

	def test_do_not_follow_on_share(self):
		user = get_user()
		event = get_event()

		share(user=user.name, doctype=event.doctype, name=event.name)

		documents_followed = get_events_followed_by_user(event.name, user.name)
		self.assertFalse(documents_followed)

	def tearDown(self):
		nts.db.rollback()
		nts.db.delete("Email Queue")
		nts.db.delete("Email Queue Recipient")
		nts.db.delete("Document Follow")
		nts.db.delete("Event")


def get_events_followed_by_user(event_name, user_name):
	DocumentFollow = DocType("Document Follow")
	return (
		nts.qb.from_(DocumentFollow)
		.where(DocumentFollow.ref_doctype == "Event")
		.where(DocumentFollow.ref_docname == event_name)
		.where(DocumentFollow.user == user_name)
		.select(DocumentFollow.name)
	).run()


def get_event():
	doc = nts.get_doc(
		{
			"doctype": "Event",
			"subject": "_Test_Doc_Follow",
			"doc.starts_on": nts.utils.now(),
			"doc.ends_on": nts.utils.add_days(nts.utils.now(), 5),
			"doc.description": "Hello",
		}
	)
	doc.insert()
	return doc


def get_user(document_follow=None):
	nts.set_user("Administrator")
	if nts.db.exists("User", "test@docsub.com"):
		doc = nts.delete_doc("User", "test@docsub.com")
	doc = nts.new_doc("User")
	doc.email = "test@docsub.com"
	doc.first_name = "Test"
	doc.last_name = "User"
	doc.send_welcome_email = 0
	doc.document_follow_notify = 1
	doc.document_follow_frequency = "Hourly"
	doc.__dict__.update(document_follow.__dict__ if document_follow else {})
	doc.insert()
	doc.add_roles("System Manager")
	return doc


def get_emails(event_doc, search_string):
	EmailQueue = DocType("Email Queue")
	EmailQueueRecipient = DocType("Email Queue Recipient")

	return (
		nts.qb.from_(EmailQueue)
		.join(EmailQueueRecipient)
		.on(EmailQueueRecipient.parent == Cast_(EmailQueue.name, "varchar"))
		.where(
			EmailQueueRecipient.recipient == "test@docsub.com",
		)
		.where(EmailQueue.message.like(f"%{event_doc.doctype}%"))
		.where(EmailQueue.message.like(f"%{event_doc.name}%"))
		.where(EmailQueue.message.like(search_string))
		.select(EmailQueue.message)
		.limit(1)
	).run()


@dataclass
class DocumentFollowConditions:
	follow_created_documents: int = 0
	follow_commented_documents: int = 0
	follow_liked_documents: int = 0
	follow_assigned_documents: int = 0
	follow_shared_documents: int = 0
