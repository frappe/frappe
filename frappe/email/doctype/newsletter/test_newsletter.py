# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals

import frappe, unittest

from frappe.email.doctype.newsletter.newsletter import unsubscribe
from urllib import unquote

class TestNewsletter(unittest.TestCase):
	def setUp(self):
		frappe.db.sql('delete from `tabEmail Group Member`')
		for email in ["test_subscriber1@example.com", "test_subscriber2@example.com", 
			"test_subscriber3@example.com"]:
				frappe.get_doc({
					"doctype": "Email Group Member",
					"email": email,
					"email_group": "_Test Email Group"
				}).insert()

	def test_send(self):
		self.send_newsletter()
		self.assertEquals(len(frappe.get_all("Email Queue")), 3)

	def test_unsubscribe(self):
		# test unsubscribe
		self.send_newsletter()

		email = unquote(frappe.local.flags.signed_query_string.split("email=")[1].split("&")[0])

		unsubscribe(email, "_Test Email Group")

		self.send_newsletter()
		self.assertEquals(len(frappe.get_all("Email Queue")), 2)

	def send_newsletter(self):
		frappe.db.sql("delete from `tabEmail Queue`")
		frappe.delete_doc("Newsletter", "_Test Newsletter")
		newsletter = frappe.get_doc({
			"doctype": "Newsletter",
			"subject": "_Test Newsletter",
			"email_group": "_Test Email Group",
			"send_from": "Test Sender <test_sender@example.com>",
			"message": "Testing my news."
		}).insert(ignore_permissions=True)

		newsletter.send_emails()

test_dependencies = ["Email Group"]
