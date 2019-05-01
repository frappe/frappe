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
		for value in frappe.get_all("Communication", filters={"sender": "test_sender@example.com"}):
			if value:
				for child in frappe.get_all("Dynamic Link", filters={"parent": value}):
					if child:
						frappe.delete_doc("Dynamic Link", child)
				frappe.delete_doc("Communication", value)

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "incoming-1.raw"), "r") as f:
			test_mails = [f.read()]

		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		comm = frappe.get_doc("Communication", {"sender": "test_sender@example.com"})
		self.assertTrue("test_receiver@example.com" in comm.recipients)

		# check if todo, contacts are created
		for links in frappe.get_list("Dynamic Link", filters={"parent": comm.name}, fields=["link_doctype", "link_name"]):
			self.assertTrue(frappe.db.get_value(links.link_doctype, links.link_name, "name"))

	def test_unread_notification(self):
		self.test_incoming()

		comm = frappe.get_doc("Communication", {"sender": "test_sender@example.com"})
		comm.db_set("creation", datetime.now() - timedelta(seconds = 30 * 60))

		frappe.db.sql("DELETE FROM `tabEmail Queue`")

		notify_unreplied()
		for links in frappe.get_list("Dynamic Link", filters={"parent": comm.name}, fields=["link_doctype", "link_name"]):
			self.assertTrue(frappe.db.get_value("Email Queue", {"reference_doctype": links.link_doctype,
				"reference_name": links.link_name, "status":"Not Sent"}))

	def test_incoming_with_attach(self):
		for value in frappe.get_all("Communication", filters={"sender": "test_sender@example.com"}):
			if value:
				for child in frappe.get_all("Dynamic Link", filters={"parent": value}):
					if child:
						frappe.delete_doc("Dynamic Link", child)
				frappe.delete_doc("Communication", value)

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
		for value in frappe.get_all("Communication", filters={"sender": "test_sender@example.com"}):
			if value:
				for child in frappe.get_all("Dynamic Link", filters={"parent": value}):
					if child:
						frappe.delete_doc("Dynamic Link", child)
				frappe.delete_doc("Communication", value)

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "incoming-3.raw"), "r") as f:
			test_mails = [f.read()]

		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		comm = frappe.get_doc("Communication", {"sender": "test_sender@example.com"})
		self.assertTrue("From: \"Microsoft Outlook\" &lt;test_sender@example.com&gt;" in comm.content)
		self.assertTrue("This is an e-mail message sent automatically by Microsoft Outlook while" in comm.content)

	def test_incoming_attached_email_from_outlook_layers(self):
		for value in frappe.get_all("Communication", filters={"sender": "test_sender@example.com"}):
			if value:
				for child in frappe.get_all("Dynamic Link", filters={"parent": value}):
					if child:
						frappe.delete_doc("Dynamic Link", child)
				frappe.delete_doc("Communication", value)

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "incoming-4.raw"), "r") as f:
			test_mails = [f.read()]

		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		comm = frappe.get_doc("Communication", {"sender": "test_sender@example.com"})
		self.assertTrue("From: \"Microsoft Outlook\" &lt;test_sender@example.com&gt;" in comm.content)
		self.assertTrue("This is an e-mail message sent automatically by Microsoft Outlook while" in comm.content)

	def test_outgoing(self):
		for value in frappe.get_all("Communication", filters={"sender": "test_sender@example.com"}):
			if value:
				for child in frappe.get_all("Dynamic Link", filters={"parent": value}):
					if child:
						frappe.delete_doc("Dynamic Link", child)
				frappe.delete_doc("Communication", value)

		make(sender="test_sender@example.com", recipients="test_receiver@example.com", subject = "test-mail-000",
		content="test mail 000", send_email=True)

		mail = email.message_from_string(frappe.get_last_doc("Email Queue").message)
		self.assertTrue("test-mail-000" in mail.get("Subject"))

	def test_sendmail(self):
		for value in frappe.get_all("Communication", filters={"sender": "test_sender@example.com"}):
			if value:
				for child in frappe.get_all("Dynamic Link", filters={"parent": value}):
					if child:
						frappe.delete_doc("Dynamic Link", child)
				frappe.delete_doc("Communication", value)

		frappe.sendmail(sender="test_sender@example.com", recipients="test_recipient@example.com",
			content="test mail 001", subject="test-mail-001", delayed=False)

		sent_mail = email.message_from_string(frappe.safe_decode(frappe.flags.sent_mail))
		self.assertTrue("test-mail-001" in sent_mail.get("Subject"))

	def test_print_format(self):
		for value in frappe.get_all("Communication", filters={"sender": "test_sender@example.com"}):
			if value:
				for child in frappe.get_all("Dynamic Link", filters={"parent": value}):
					if child:
						frappe.delete_doc("Dynamic Link", child)
				frappe.delete_doc("Communication", value)

		make(sender="test_sender@example.com", recipients="test_recipient@example.com",
			content="test mail 001", subject="test-mail-002", doctype="Email Account",
			name="_Test Email Account 1", print_format="Standard", send_email=True)

		sent_mail = email.message_from_string(frappe.get_last_doc("Email Queue").message)
		self.assertTrue("test-mail-002" in sent_mail.get("Subject"))

	def test_threading(self):
		for value in frappe.get_all("Communication", filters={"sender": "test@example.com"}):
			if value:
				for child in frappe.get_all("Dynamic Link", filters={"parent": value}):
					if child:
						frappe.delete_doc("Dynamic Link", child)
				frappe.delete_doc("Communication", value)

		# send
		sent_name = make(subject = "Test", content="test content", recipients="test_receiver@example.com",
			sender="test@example.com", doctype="ToDo", name=frappe.get_last_doc("ToDo").name, send_email=True)["name"]

		sent_mail = email.message_from_string(frappe.get_last_doc("Email Queue").message)

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "reply-1.raw"), "r") as f:
			raw = f.read()
			raw = raw.replace("<-- in-reply-to -->", sent_mail.get("Message-Id"))
			test_mails = [raw]

		# parse reply
		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		sent = frappe.get_doc("Communication", sent_name)
		sent_links = frappe.get_list("Dynamic Link", filters={"parent": sent.name}, fields=["link_doctype", "link_name"])

		comm = frappe.get_doc("Communication", {"sender": "test@example.com"})
		comm_links = frappe.get_list("Dynamic Link", filters={"parent": comm.name}, fields=["link_doctype", "link_name"])

		length = max(len(sent_links), len(comm_links))
		for idx in range(0, int(length/2)):
			self.assertTrue(sent_links[idx].link_doctype, comm_links[idx].link_doctype)

	def test_threading_by_subject(self):
		for value in frappe.get_all("Communication", filters={"sender": "test_sender@example.com"}, or_filters={"sender": "test@example.com"}):
			if value:
				for child in frappe.get_all("Dynamic Link", filters={"parent": value}):
					if child:
						frappe.delete_doc("Dynamic Link", child)
				frappe.delete_doc("Communication", value)

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "reply-2.raw"), "r") as f:
			test_mails = [f.read()]

		with open(os.path.join(os.path.dirname(__file__), "test_mails", "reply-3.raw"), "r") as f:
			test_mails.append(f.read())

		# parse reply
		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		comm_lists = frappe.get_all("Communication", filters={"sender":"test_sender@example.com"}, fields=["name"])

		comm_links = []
		for comm_list in comm_lists:
			for links in frappe.get_list("Dynamic Link", filters={"parent": comm_list.name}, fields=["link_doctype", "link_name"]):
		 		comm_links.append(links)

		# both communications attached to the same reference
		counter = 0
		for comm_link_1 in comm_links:
			for comm_link_2 in comm_links:
				if comm_link_1.link_doctype == comm_link_2.link_doctype and \
					comm_link_1.link_name == comm_link_2.link_name:
					counter += 1
					break

		self.assertEqual(len(comm_links), counter)

	def test_threading_by_message_id(self):
		for value in frappe.get_all("Communication"):
			if value:
				for child in frappe.get_all("Dynamic Link", filters={"parent": value}):
					if child:
						frappe.delete_doc("Dynamic Link", child)
				frappe.delete_doc("Communication", value)
		frappe.db.sql("""delete from `tabEmail Queue`""")

		# reference document for testing
		event = frappe.get_doc(dict(doctype='Event', subject='test-message')).insert()

		# send a mail against this
		frappe.sendmail(recipients='test@example.com', subject='test message for threading',
			message='testing', link_doctype=event.doctype, link_name=event.name)

		last_mail = frappe.get_doc('Email Queue', dict(reference_name=event.name))

		# get test mail with message-id as in-reply-to
		with open(os.path.join(os.path.dirname(__file__), "test_mails", "reply-4.raw"), "r") as f:
			test_mails = [f.read().replace('{{ message_id }}', last_mail.message_id)]

		# pull the mail
		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.receive(test_mails=test_mails)

		comm_lists = frappe.get_all("Communication", filters={"sender":"test_sender@example.com"}, fields=["name"])

		comm_links = []
		for comm_list in comm_lists:
			for links in frappe.get_list("Dynamic Link", filters={"parent": comm_list.name}, fields=["link_doctype", "link_name"]):
		 		comm_links.append(links)

		# check if threaded correctly
		counter = 0
		for comm_link_1 in comm_links:
			for comm_link_2 in comm_links:
				if comm_link_1.link_doctype == comm_link_2.link_doctype and \
					comm_link_1.link_name == comm_link_2.link_name:
					counter += 1
					break

		self.assertEqual(len(comm_links), counter)