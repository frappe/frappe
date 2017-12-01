# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals

import frappe, unittest

from frappe.email.doctype.newsletter.newsletter import confirmed_unsubscribe
from six.moves.urllib.parse import unquote


emails = ["test_subscriber1@example.com", "test_subscriber2@example.com",
			"test_subscriber3@example.com", "test1@example.com"]

class TestNewsletter(unittest.TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.sql('delete from `tabEmail Group Member`')
		for email in emails:
				frappe.get_doc({
					"doctype": "Email Group Member",
					"email": email,
					"email_group": "_Test Email Group"
				}).insert()

	def test_send(self):
		name = self.send_newsletter()

		email_queue_list = [frappe.get_doc('Email Queue', e.name) for e in frappe.get_all("Email Queue")]
		self.assertEquals(len(email_queue_list), 4)
		recipients = [e.recipients[0].recipient for e in email_queue_list]
		for email in emails:
			self.assertTrue(email in recipients)

	def test_unsubscribe(self):
		# test unsubscribe
		name = self.send_newsletter()
		from frappe.email.queue import flush
		flush(from_test=True)
		to_unsubscribe = unquote(frappe.local.flags.signed_query_string.split("email=")[1].split("&")[0])

		confirmed_unsubscribe(to_unsubscribe, name)

		name = self.send_newsletter()

		email_queue_list = [frappe.get_doc('Email Queue', e.name) for e in frappe.get_all("Email Queue")]
		self.assertEquals(len(email_queue_list), 3)
		recipients = [e.recipients[0].recipient for e in email_queue_list]
		for email in emails:
			if email != to_unsubscribe:
				self.assertTrue(email in recipients)

	@staticmethod
	def send_newsletter(published=0):
		frappe.db.sql("delete from `tabEmail Queue`")
		frappe.db.sql("delete from `tabEmail Queue Recipient`")
		frappe.db.sql("delete from `tabNewsletter`")
		newsletter = frappe.get_doc({
			"doctype": "Newsletter",
			"subject": "_Test Newsletter",
			"send_from": "Test Sender <test_sender@example.com>",
			"message": "Testing my news.",
			"published": published
		}).insert(ignore_permissions=True)

		newsletter.append("email_group", {"email_group": "_Test Email Group"})
		newsletter.save()
		newsletter.send_emails()
		return newsletter.name

	def test_portal(self):
		self.send_newsletter(1)
		frappe.set_user("test1@example.com")
		from frappe.email.doctype.newsletter.newsletter import get_newsletter_list
		newsletters = get_newsletter_list("Newsletter", None, None, 0)
		self.assertEquals(len(newsletters), 1)

	def test_newsletter_context(self):
		context = frappe._dict()
		newsletter_name = self.send_newsletter(1)
		frappe.set_user("test2@example.com")
		doc = frappe.get_doc("Newsletter", newsletter_name)
		doc.get_context(context)
		self.assertEquals(context.no_cache, 1)
		self.assertTrue("attachments" not in context.keys())


test_dependencies = ["Email Group"]
