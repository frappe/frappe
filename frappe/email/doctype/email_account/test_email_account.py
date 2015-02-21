# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe, os
import unittest, email

test_records = frappe.get_test_records('Email Account')

from frappe.core.doctype.communication.communication import make
from frappe.desk.form.load import get_attachments
from frappe.utils.file_manager import delete_file_from_filesystem

class TestEmailAccount(unittest.TestCase):
	def test_incoming(self):
		frappe.db.sql("delete from tabCommunication where sender='test_sender@example.com'")

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "incoming-1.raw"), "r") as f:
			test_mails = [f.read()]

		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		comm = frappe.get_doc("Communication", {"sender": "test_sender@example.com"})
		self.assertTrue("test_receiver@example.com" in comm.recipients)

	def test_incoming_with_attach(self):
		frappe.db.sql("delete from tabCommunication where sender='test_sender@example.com'")
		existing_file = frappe.get_doc({'doctype': 'File Data', 'file_name': 'erpnext-conf-14.png'})
		frappe.delete_doc("File Data", existing_file.name)
		delete_file_from_filesystem(existing_file)

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "incoming-2.raw"), "r") as f:
			test_mails = [f.read()]

		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		comm = frappe.get_doc("Communication", {"sender": "test_sender@example.com"})
		self.assertTrue("test_receiver@example.com" in comm.recipients)

		# check attachment
		attachments = get_attachments(comm.doctype, comm.name)
		self.assertTrue("erpnext-conf-14.png" in [f.file_name for f in attachments])

	def test_outgoing(self):
		frappe.flags.sent_mail = None
		make(subject = "test-mail-000", content="test mail 000", recipients="test_receiver@example.com",
			send_email=True, sender="test_sender@example.com")

		mail = email.message_from_string(frappe.get_last_doc("Bulk Email").message)
		self.assertTrue("test-mail-000" in mail.get("Subject"))

	def test_sendmail(self):
		frappe.flags.sent_mail = None
		frappe.sendmail(sender="test_sender@example.com", recipients="test_recipient@example.com",
			content="test mail 001", subject="test-mail-001")

		sent_mail = email.message_from_string(frappe.flags.sent_mail)
		self.assertTrue("test-mail-001" in sent_mail.get("Subject"))

	def test_print_format(self):
		frappe.flags.sent_mail = None
		make(sender="test_sender@example.com", recipients="test_recipient@example.com",
			content="test mail 001", subject="test-mail-002", doctype="Email Account",
			name="_Test Email Account 1", print_format="Standard", send_email=True)

		sent_mail = email.message_from_string(frappe.get_last_doc("Bulk Email").message)
		self.assertTrue("test-mail-002" in sent_mail.get("Subject"))

	def test_threading(self):
		frappe.db.sql("""delete from tabCommunication
			where sender in ('test_sender@example.com', 'test@example.com')""")

		# send
		sent_name = make(subject = "Test", content="test content",
			recipients="test_receiver@example.com", sender="test@example.com",
			send_email=True)

		sent_mail = email.message_from_string(frappe.get_last_doc("Bulk Email").message)
		with open(os.path.join(os.path.dirname(__file__), "test_mails", "reply-1.raw"), "r") as f:
			raw = f.read()
			raw = raw.replace("<-- in-reply-to -->", sent_mail.get("Message-Id"))
			test_mails = [raw]

		# parse reply
		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		sent = frappe.get_doc("Communication", sent_name)

		comm = frappe.get_doc("Communication", {"sender": "test_sender@example.com"})
		self.assertEquals(comm.reference_doctype, sent.doctype)
		self.assertEquals(comm.reference_name, sent.name)





