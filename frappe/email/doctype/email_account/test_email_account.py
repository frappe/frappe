# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals
import frappe, os
import unittest, email

test_records = frappe.get_test_records('Email Account')

from frappe.core.doctype.communication.email import make
from frappe.desk.form.load import get_attachments
from frappe.email.doctype.email_account.email_account import notify_unreplied
from datetime import datetime, timedelta

class TestEmailAccount(unittest.TestCase):
	def setUp(self):
		frappe.flags.mute_emails = False
		frappe.flags.sent_mail = None

		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.db_set("enable_incoming", 1)
		frappe.db.sql('delete from `tabEmail Queue`')

	def tearDown(self):
		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.db_set("enable_incoming", 0)

	def test_incoming(self):
		frappe.db.sql("delete from tabCommunication where sender='test_sender@example.com'")

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "incoming-1.raw"), "r") as f:
			test_mails = [f.read()]

		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		comm = frappe.get_doc("Communication", {"sender": "test_sender@example.com"})
		self.assertTrue("test_receiver@example.com" in comm.recipients)

		# check if todo is created
		self.assertTrue(frappe.db.get_value(comm.reference_doctype, comm.reference_name, "name"))

	def test_unread_notification(self):
		self.test_incoming()

		comm = frappe.get_doc("Communication", {"sender": "test_sender@example.com"})
		comm.db_set("creation", datetime.now() - timedelta(seconds = 30 * 60))

		frappe.db.sql("DELETE FROM `tabEmail Queue`")
		notify_unreplied()
		self.assertTrue(frappe.db.get_value("Email Queue", {"reference_doctype": comm.reference_doctype,
			"reference_name": comm.reference_name, "status":"Not Sent"}))

	def test_incoming_with_attach(self):
		frappe.db.sql("DELETE FROM `tabCommunication` WHERE sender='test_sender@example.com'")
		existing_file = frappe.get_doc({'doctype': 'File', 'file_name': 'erpnext-conf-14.png'})
		frappe.delete_doc("File", existing_file.name)

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "incoming-2.raw"), "r") as testfile:
			test_mails = [testfile.read()]

		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		comm = frappe.get_doc("Communication", {"sender": "test_sender@example.com"})
		self.assertTrue("test_receiver@example.com" in comm.recipients)

		# check attachment
		attachments = get_attachments(comm.doctype, comm.name)
		self.assertTrue("erpnext-conf-14.png" in [f.file_name for f in attachments])

		# cleanup
		existing_file = frappe.get_doc({'doctype': 'File', 'file_name': 'erpnext-conf-14.png'})
		frappe.delete_doc("File", existing_file.name)


	def test_incoming_attached_email_from_outlook_plain_text_only(self):
		frappe.db.sql("delete from tabCommunication where sender='test_sender@example.com'")

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "incoming-3.raw"), "r") as f:
			test_mails = [f.read()]

		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		comm = frappe.get_doc("Communication", {"sender": "test_sender@example.com"})
		self.assertTrue("From: \"Microsoft Outlook\" &lt;test_sender@example.com&gt;" in comm.content)
		self.assertTrue("This is an e-mail message sent automatically by Microsoft Outlook while" in comm.content)

	def test_incoming_attached_email_from_outlook_layers(self):
		frappe.db.sql("delete from tabCommunication where sender='test_sender@example.com'")

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "incoming-4.raw"), "r") as f:
			test_mails = [f.read()]

		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		comm = frappe.get_doc("Communication", {"sender": "test_sender@example.com"})
		self.assertTrue("From: \"Microsoft Outlook\" &lt;test_sender@example.com&gt;" in comm.content)
		self.assertTrue("This is an e-mail message sent automatically by Microsoft Outlook while" in comm.content)

	def test_outgoing(self):
		make(subject = "test-mail-000", content="test mail 000", recipients="test_receiver@example.com",
			send_email=True, sender="test_sender@example.com")

		mail = email.message_from_string(frappe.get_last_doc("Email Queue").message)
		self.assertTrue("test-mail-000" in mail.get("Subject"))

	def test_sendmail(self):
		frappe.sendmail(sender="test_sender@example.com", recipients="test_recipient@example.com",
			content="test mail 001", subject="test-mail-001", delayed=False)

		sent_mail = email.message_from_string(frappe.safe_decode(frappe.flags.sent_mail))
		self.assertTrue("test-mail-001" in sent_mail.get("Subject"))

	def test_print_format(self):
		make(sender="test_sender@example.com", recipients="test_recipient@example.com",
			content="test mail 001", subject="test-mail-002", doctype="Email Account",
			name="_Test Email Account 1", print_format="Standard", send_email=True)

		sent_mail = email.message_from_string(frappe.get_last_doc("Email Queue").message)
		self.assertTrue("test-mail-002" in sent_mail.get("Subject"))

	def test_threading(self):
		frappe.db.sql("""delete from tabCommunication
			where sender in ('test_sender@example.com', 'test@example.com')""")

		# send
		sent_name = make(subject = "Test", content="test content",
			recipients="test_receiver@example.com", sender="test@example.com",doctype="ToDo",name=frappe.get_last_doc("ToDo").name,
			send_email=True)["name"]

		sent_mail = email.message_from_string(frappe.get_last_doc("Email Queue").message)

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "reply-1.raw"), "r") as f:
			raw = f.read()
			raw = raw.replace("<-- in-reply-to -->", sent_mail.get("Message-Id"))
			test_mails = [raw]

		# parse reply
		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		sent = frappe.get_doc("Communication", sent_name)

		comm = frappe.get_doc("Communication", {"sender": "test_sender@example.com"})
		self.assertEqual(comm.reference_doctype, sent.reference_doctype)
		self.assertEqual(comm.reference_name, sent.reference_name)

	def test_threading_by_subject(self):
		frappe.db.sql("""delete from tabCommunication
			where sender in ('test_sender@example.com', 'test@example.com')""")

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "reply-2.raw"), "r") as f:
			test_mails = [f.read()]

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "reply-3.raw"), "r") as f:
			test_mails.append(f.read())

		# parse reply
		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		comm_list = frappe.get_all("Communication", filters={"sender":"test_sender@example.com"},
			fields=["name", "reference_doctype", "reference_name"])

		# both communications attached to the same reference
		self.assertEqual(comm_list[0].reference_doctype, comm_list[1].reference_doctype)
		self.assertEqual(comm_list[0].reference_name, comm_list[1].reference_name)

	def test_threading_by_message_id(self):
		frappe.db.sql("""delete from tabCommunication""")
		frappe.db.sql("""delete from `tabEmail Queue`""")

		# reference document for testing
		event = frappe.get_doc(dict(doctype='Event', subject='test-message')).insert()

		# send a mail against this
		frappe.sendmail(recipients='test@example.com', subject='test message for threading',
			message='testing', reference_doctype=event.doctype, reference_name=event.name)

		last_mail = frappe.get_doc('Email Queue', dict(reference_name=event.name))

		# get test mail with message-id as in-reply-to
		with open(os.path.join(os.path.dirname(__file__), "test_mails", "reply-4.raw"), "r") as f:
			test_mails = [f.read().replace('{{ message_id }}', last_mail.message_id)]

		# pull the mail
		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		comm_list = frappe.get_all("Communication", filters={"sender":"test_sender@example.com"},
			fields=["name", "reference_doctype", "reference_name"])

		# check if threaded correctly
		self.assertEqual(comm_list[0].reference_doctype, event.doctype)
		self.assertEqual(comm_list[0].reference_name, event.name)
