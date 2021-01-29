# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals

import unittest
from random import choice

import frappe
from frappe.email.doctype.newsletter.newsletter import (
	confirmed_unsubscribe,
	send_scheduled_email,
)
from frappe.email.doctype.newsletter.newsletter import get_newsletter_list
from frappe.email.queue import flush
from frappe.utils import add_days, getdate

test_dependencies = ["Email Group"]
emails = [
	"test_subscriber1@example.com",
	"test_subscriber2@example.com",
	"test_subscriber3@example.com",
	"test1@example.com",
]


class TestNewsletter(unittest.TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.sql("delete from `tabEmail Group Member`")

		if not frappe.db.exists("Email Group", "_Test Email Group"):
			frappe.get_doc({"doctype": "Email Group", "title": "_Test Email Group"}).insert()

		for email in emails:
			frappe.get_doc({
				"doctype": "Email Group Member",
				"email": email,
				"email_group": "_Test Email Group"
			}).insert()

	def test_send(self):
		self.send_newsletter()

		email_queue_list = [frappe.get_doc("Email Queue", e.name) for e in frappe.get_all("Email Queue")]
		self.assertEqual(len(email_queue_list), 4)

		recipients = set([e.recipients[0].recipient for e in email_queue_list])
		self.assertTrue(set(emails).issubset(recipients))

	def test_unsubscribe(self):
		name = self.send_newsletter()
		to_unsubscribe = choice(emails)
		group = frappe.get_all("Newsletter Email Group", filters={"parent": name}, fields=["email_group"])

		flush(from_test=True)
		confirmed_unsubscribe(to_unsubscribe, group[0].email_group)

		name = self.send_newsletter()
		email_queue_list = [
			frappe.get_doc("Email Queue", e.name) for e in frappe.get_all("Email Queue")
		]
		self.assertEqual(len(email_queue_list), 3)
		recipients = [e.recipients[0].recipient for e in email_queue_list]

		for email in emails:
			if email != to_unsubscribe:
				self.assertTrue(email in recipients)

	@staticmethod
	def send_newsletter(published=0, schedule_send=None):
		frappe.db.sql("delete from `tabEmail Queue`")
		frappe.db.sql("delete from `tabEmail Queue Recipient`")
		frappe.db.sql("delete from `tabNewsletter`")
		newsletter = frappe.get_doc({
			"doctype": "Newsletter",
			"subject": "_Test Newsletter",
			"send_from": "Test Sender <test_sender@example.com>",
			"content_type": "Rich Text",
			"message": "Testing my news.",
			"published": published,
			"schedule_sending": bool(schedule_send),
			"schedule_send": schedule_send
		}).insert(ignore_permissions=True)

		newsletter.append("email_group", {"email_group": "_Test Email Group"})
		newsletter.save()
		if schedule_send:
			send_scheduled_email()
			return

		newsletter.send_emails()
		return newsletter.name

	def test_portal(self):
		self.send_newsletter(1)
		frappe.set_user("test1@example.com")
		newsletters = get_newsletter_list("Newsletter", None, None, 0)
		self.assertEqual(len(newsletters), 1)

	def test_newsletter_context(self):
		context = frappe._dict()
		newsletter_name = self.send_newsletter(1)
		frappe.set_user("test2@example.com")
		doc = frappe.get_doc("Newsletter", newsletter_name)
		doc.get_context(context)
		self.assertEqual(context.no_cache, 1)
		self.assertTrue("attachments" not in list(context))

	def test_schedule_send(self):
		self.send_newsletter(schedule_send=add_days(getdate(), -1))

		email_queue_list = [frappe.get_doc('Email Queue', e.name) for e in frappe.get_all("Email Queue")]
		self.assertEqual(len(email_queue_list), 4)
		recipients = [e.recipients[0].recipient for e in email_queue_list]
		for email in emails:
			self.assertTrue(email in recipients)
