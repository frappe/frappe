# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals

import frappe, unittest

from frappe.email.doctype.newsletter.newsletter import confirmed_unsubscribe
from urllib import unquote

emails = ["test_subscriber1@example.com", "test_subscriber2@example.com",
			"test_subscriber3@example.com"]

class TestNewsletter(unittest.TestCase):
	def setUp(self):
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
		self.assertEquals(len(email_queue_list), 3)
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
		self.assertEquals(len(email_queue_list), 2)
		recipients = [e.recipients[0].recipient for e in email_queue_list]
		for email in emails:
			if email != to_unsubscribe:
				self.assertTrue(email in recipients)

	def send_newsletter(self):
		frappe.db.sql("delete from `tabEmail Queue`")
		frappe.db.sql("delete from `tabEmail Queue Recipient`")
		frappe.db.sql("delete from `tabNewsletter`")
		newsletter = frappe.get_doc({
			"doctype": "Newsletter",
			"subject": "_Test Newsletter",
			"send_from": "Test Sender <test_sender@example.com>",
			"message": "Testing my news."
		}).insert(ignore_permissions=True)

		newsletter.append("email_group", {"email_group": "_Test Email Group"})
		newsletter.save()
		newsletter.send_emails()
		return newsletter.name

test_dependencies = ["Email Group"]
