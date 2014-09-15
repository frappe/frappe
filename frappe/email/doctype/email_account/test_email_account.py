# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
import unittest

test_records = frappe.get_test_records('Email Account')

from frappe.core.doctype.communication.communication import make

class TestEmailAccount(unittest.TestCase):
	def test_incoming(self):
		frappe.db.sql("delete from tabCommunication where sender='test_sender@example.com'")

		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive()

		comm = frappe.get_doc("Communication", {"sender": "test_sender@example.com"})
		self.assertTrue("test_receiver@example.com" in comm.recipients)

	def test_outgoing(self):
		make(subject = "Test", content="test content", recipients="test_receiver@example.com",
			send_email=True)

		self.assertTrue(frappe.flags.sent_mail)


