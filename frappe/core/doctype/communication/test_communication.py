# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from typing import TYPE_CHECKING

import frappe
from frappe.core.doctype.communication.communication import Communication, get_emails, parse_email
from frappe.core.doctype.communication.email import add_attachments, make
from frappe.email.doctype.email_queue.email_queue import EmailQueue
from frappe.tests import IntegrationTestCase, UnitTestCase

if TYPE_CHECKING:
	from frappe.contacts.doctype.contact.contact import Contact
	from frappe.email.doctype.email_account.email_account import EmailAccount


class UnitTestCommunication(UnitTestCase):
	"""
	Unit tests for Communication.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestCommunication(IntegrationTestCase):
	def test_email(self):
		valid_email_list = [
			"Full Name <full@example.com>",
			'"Full Name with quotes and <weird@chars.com>" <weird@example.com>',
			"Surname, Name <name.surname@domain.com>",
			"Purchase@ABC <purchase@abc.com>",
			"xyz@abc2.com <xyz@abc.com>",
			"Name [something else] <name@domain.com>",
		]

		invalid_email_list = [
			"[invalid!email]",
			"invalid-email",
			"tes2",
			"e",
			"rrrrrrrr",
			"manas",
			"[[[sample]]]",
			"[invalid!email].com",
		]

		for i, x in enumerate(valid_email_list):
			with self.subTest(i=i, x=x):
				self.assertTrue(frappe.utils.parse_addr(x)[1])

		for i, x in enumerate(invalid_email_list):
			with self.subTest(i=i, x=x):
				self.assertFalse(frappe.utils.parse_addr(x)[0])

	def test_name(self):
		valid_email_list = [
			"Full Name <full@example.com>",
			'"Full Name with quotes and <weird@chars.com>" <weird@example.com>',
			"Surname, Name <name.surname@domain.com>",
			"Purchase@ABC <purchase@abc.com>",
			"xyz@abc2.com <xyz@abc.com>",
			"Name [something else] <name@domain.com>",
		]

		invalid_email_list = [
			"[invalid!email]",
			"invalid-email",
			"tes2",
			"e",
			"rrrrrrrr",
			"manas",
			"[[[sample]]]",
			"[invalid!email].com",
		]

		for x in valid_email_list:
			self.assertTrue(frappe.utils.parse_addr(x)[0])

		for x in invalid_email_list:
			self.assertFalse(frappe.utils.parse_addr(x)[0])

	def test_circular_linking(self):
		a = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"content": "This was created to test circular linking: Communication A",
			}
		).insert(ignore_permissions=True)

		b = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"content": "This was created to test circular linking: Communication B",
				"reference_doctype": "Communication",
				"reference_name": a.name,
			}
		).insert(ignore_permissions=True)

		c = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"content": "This was created to test circular linking: Communication C",
				"reference_doctype": "Communication",
				"reference_name": b.name,
			}
		).insert(ignore_permissions=True)

		a = frappe.get_doc("Communication", a.name)
		a.reference_doctype = "Communication"
		a.reference_name = c.name

		self.assertRaises(frappe.CircularLinkingError, a.save)

	def test_deduplication_timeline_links(self):
		frappe.delete_doc_if_exists("Note", "deduplication timeline links")

		note = frappe.get_doc(
			{
				"doctype": "Note",
				"title": "deduplication timeline links",
				"content": "deduplication timeline links",
			}
		).insert(ignore_permissions=True)

		comm = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"content": "Deduplication of Links",
				"communication_medium": "Email",
			}
		).insert(ignore_permissions=True)

		# adding same link twice
		comm.add_link(link_doctype="Note", link_name=note.name, autosave=True)
		comm.add_link(link_doctype="Note", link_name=note.name, autosave=True)

		comm = frappe.get_doc("Communication", comm.name)

		self.assertNotEqual(2, len(comm.timeline_links))

	def test_contacts_attached(self):
		contact_sender: "Contact" = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "contact_sender",
			}
		)
		contact_sender.add_email("comm_sender@example.com")
		contact_sender.insert(ignore_permissions=True)

		contact_recipient: "Contact" = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "contact_recipient",
			}
		)
		contact_recipient.add_email("comm_recipient@example.com")
		contact_recipient.insert(ignore_permissions=True)

		contact_cc: "Contact" = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "contact_cc",
			}
		)
		contact_cc.add_email("comm_cc@example.com")
		contact_cc.insert(ignore_permissions=True)

		comm: Communication = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_medium": "Email",
				"subject": "Contacts Attached Test",
				"sender": "comm_sender@example.com",
				"recipients": "comm_recipient@example.com",
				"cc": "comm_cc@example.com",
			}
		).insert(ignore_permissions=True)

		comm = frappe.get_doc("Communication", comm.name)
		contact_links = [x.link_name for x in comm.timeline_links]

		self.assertIn(contact_sender.name, contact_links)
		self.assertIn(contact_recipient.name, contact_links)
		self.assertIn(contact_cc.name, contact_links)

	def test_get_communication_data(self):
		from frappe.desk.form.load import get_communication_data

		frappe.delete_doc_if_exists("Note", "get communication data")

		note = frappe.get_doc(
			{"doctype": "Note", "title": "get communication data", "content": "get communication data"}
		).insert(ignore_permissions=True)

		comm_note_1 = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"content": "Test Get Communication Data 1",
				"communication_medium": "Email",
			}
		).insert(ignore_permissions=True)

		comm_note_1.add_link(link_doctype="Note", link_name=note.name, autosave=True)

		comm_note_2 = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"content": "Test Get Communication Data 2",
				"communication_medium": "Email",
			}
		).insert(ignore_permissions=True)

		comm_note_2.add_link(link_doctype="Note", link_name=note.name, autosave=True)

		comms = get_communication_data("Note", note.name, as_dict=True)

		data = [comm.name for comm in comms]
		self.assertIn(comm_note_1.name, data)
		self.assertIn(comm_note_2.name, data)

	def test_parse_email(self):
		to = "Jon Doe <jon.doe@example.org>"
		cc = """=?UTF-8?Q?Max_Mu=C3=9F?= <max.muss@examle.org>,
	erp+Customer=Plus%2BCompany@example.org,
	erp+Customer+Space%20Company@example.org,
	erp+Customer+Space+Company+Plus+Encoded@example.org"""
		bcc = ""

		results = list(parse_email([to, cc, bcc]))
		self.assertEqual(
			[
				("Customer", "Plus+Company"),
				("Customer", "Space Company"),
				("Customer", "Space Company Plus Encoded"),
			],
			results,
		)

		results = list(parse_email([to, bcc]))
		self.assertEqual(results, [])

		to = "jane.doe+A+Test@example.org"
		cc = ""
		bcc = "=?UTF-8?Q?Max_Mu=C3=9F?= <max.muss+Note=Very%20important@examle.org>"
		results = list(parse_email([to, cc, bcc]))
		self.assertEqual([("A", "Test"), ("Note", "Very important")], results)

	def test_get_emails(self):
		emails = get_emails(
			[
				"comm_recipient+DocType+DocName@example.com",
				'"First, LastName" <first.lastname@email.com>',
				"test@user.com",
			]
		)

		self.assertEqual(emails[0], "comm_recipient+DocType+DocName@example.com")
		self.assertEqual(emails[1], "first.lastname@email.com")
		self.assertEqual(emails[2], "test@user.com")

	def test_signature_in_email_content(self):
		email_account = create_email_account()
		signature = email_account.signature
		base_communication = {
			"doctype": "Communication",
			"communication_medium": "Email",
			"subject": "Document Link in Email",
			"sender": "comm_sender@example.com",
		}
		comm_with_signature = frappe.get_doc(
			base_communication
			| {
				"content": f"""<div class="ql-editor read-mode">
				Hi,
				How are you?
				</div><p></p><br><p class="signature">{signature}</p>""",
			}
		).insert(ignore_permissions=True)
		comm_without_signature = frappe.get_doc(
			base_communication
			| {
				"content": """<div class="ql-editor read-mode">
				Hi,
				How are you?
				</div>"""
			}
		).insert(ignore_permissions=True)

		self.assertEqual(comm_with_signature.content, comm_without_signature.content)
		self.assertEqual(comm_with_signature.content.count(signature), 1)
		self.assertEqual(comm_without_signature.content.count(signature), 1)

	def test_mark_as_spam(self):
		frappe.get_doc(
			{
				"doctype": "Email Rule",
				"email_id": "spammer@example.com",
				"is_spam": 1,
			}
		).insert(ignore_permissions=True)

		spam_comm: Communication = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_medium": "Email",
				"subject": "This is spam",
				"sender": "spammer@example.com",
				"recipients": "comm_recipient@example.com",
				"sent_or_received": "Received",
			}
		).insert(ignore_permissions=True)

		self.assertEqual(spam_comm.email_status, "Spam")

		normal_comm: Communication = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_medium": "Email",
				"subject": "This is spam",
				"sender": "friendlyhuman@example.com",
				"recipients": "comm_recipient@example.com",
				"sent_or_received": "Received",
			}
		).insert(ignore_permissions=True)
		self.assertNotEqual(normal_comm.email_status, "Spam")


class TestCommunicationEmailMixin(IntegrationTestCase):
	def new_communication(self, recipients=None, cc=None, bcc=None) -> Communication:
		recipients = ", ".join(recipients or [])
		cc = ", ".join(cc or [])
		bcc = ", ".join(bcc or [])

		return frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"communication_medium": "Email",
				"content": "Test content",
				"recipients": recipients,
				"cc": cc,
				"bcc": bcc,
				"sender": "sender@test.com",
			}
		).insert(ignore_permissions=True)

	def new_user(self, email, **user_data):
		user_data.setdefault("first_name", "first_name")
		user = frappe.new_doc("User")
		user.email = email
		user.update(user_data)
		user.insert(ignore_permissions=True, ignore_if_duplicate=True)
		return user

	def test_recipients(self):
		to_list = ["to@test.com", "receiver <to+1@test.com>", "to@test.com"]
		comm = self.new_communication(recipients=to_list)
		res = comm.get_mail_recipients_with_displayname()
		self.assertCountEqual(res, ["to@test.com", "receiver <to+1@test.com>"])
		comm.delete()

	def test_cc(self):
		def test(assertion, cc_list=None, set_user_as=None, include_sender=False, thread_notify=False):
			if set_user_as:
				frappe.set_user(set_user_as)

			user = self.new_user(email="cc+1@test.com", thread_notify=thread_notify)
			comm = self.new_communication(recipients=["to@test.com"], cc=cc_list)
			res = comm.get_mail_cc_with_displayname(include_sender=include_sender)

			frappe.set_user("Administrator")
			user.delete()
			comm.delete()

			self.assertEqual(res, assertion)

		# test filter_thread_notification_disbled_users and filter_mail_recipients
		test(["cc <cc+2@test.com>"], cc_list=["cc+1@test.com", "cc <cc+2@test.com>", "to@test.com"])

		# test include_sender
		test(["sender@test.com"], include_sender=True, thread_notify=True)
		test(["cc+1@test.com"], include_sender=True, thread_notify=True, set_user_as="cc+1@test.com")

	def test_bcc(self):
		bcc_list = [
			"bcc+1@test.com",
			"cc <bcc+2@test.com>",
		]
		user = self.new_user(email="bcc+2@test.com", enabled=0)
		comm = self.new_communication(bcc=bcc_list)
		res = comm.get_mail_bcc_with_displayname()
		# Disabled users have thread_notify disabled, so they'll be removed from the list
		self.assertCountEqual(res, bcc_list[:1])
		user.delete()
		comm.delete()

	def test_sendmail(self):
		to_list = ["to <to@test.com>"]
		cc_list = ["cc <cc+1@test.com>", "cc <cc+2@test.com>"]

		comm = self.new_communication(recipients=to_list, cc=cc_list)
		comm.send_email()
		doc = EmailQueue.find_one_by_filters(communication=comm.name)
		mail_receivers = [each.recipient for each in doc.recipients]
		self.assertIsNotNone(doc)
		self.assertCountEqual(to_list + cc_list, mail_receivers)
		doc.delete()
		comm.delete()

	def test_add_attachments_by_filename(self):
		to_list = ["to <to@test.com>"]
		comm = self.new_communication(recipients=to_list)

		file = frappe.new_doc("File")
		file.file_name = "test_add_attachments_by_filename.txt"
		file.content = "test_add_attachments_by_filename"
		file.insert(ignore_permissions=True)

		add_attachments(comm.name, [file.name])

		attached_file_name, attached_content_hash = frappe.db.get_value(
			"File",
			{"attached_to_name": comm.name, "attached_to_doctype": comm.doctype},
			["file_name", "content_hash"],
		)
		self.assertEqual(attached_content_hash, file.content_hash)
		self.assertEqual(attached_file_name, file.file_name)

	def test_add_attachments_by_file_content(self):
		to_list = ["to <to@test.com>"]
		comm = self.new_communication(recipients=to_list)
		file_name = "test_add_attachments_by_file_content.txt"
		file_content = "test_add_attachments_by_file_content"
		add_attachments(comm.name, [{"fcontent": file_content, "fname": file_name}])
		attached_file_name = frappe.db.get_value(
			"File",
			{"attached_to_name": comm.name, "attached_to_doctype": comm.doctype},
		)
		attached_file = frappe.get_doc("File", attached_file_name)
		self.assertEqual(attached_file.file_name, file_name)
		self.assertEqual(attached_file.get_content(), file_content)


def create_email_account() -> "EmailAccount":
	frappe.delete_doc_if_exists("Email Account", "_Test Comm Account 1")

	frappe.flags.mute_emails = False
	frappe.flags.sent_mail = None

	return frappe.get_doc(
		{
			"is_default": 1,
			"is_global": 1,
			"doctype": "Email Account",
			"domain": "example.com",
			"append_to": "ToDo",
			"email_account_name": "_Test Comm Account 1",
			"enable_outgoing": 1,
			"default_outgoing": 1,
			"smtp_server": "test.example.com",
			"email_id": "test_comm@example.com",
			"password": "password",
			"add_signature": 1,
			"signature": "\nBest Wishes\nTest Signature",
			"enable_auto_reply": 1,
			"auto_reply_message": "",
			"enable_incoming": 1,
			"notify_if_unreplied": 1,
			"unreplied_for_mins": 20,
			"send_notification_to": "test_comm@example.com",
			"pop3_server": "pop.test.example.com",
			"imap_folder": [{"folder_name": "INBOX", "append_to": "ToDo"}],
			"enable_automatic_linking": 1,
		}
	).insert(ignore_permissions=True)
