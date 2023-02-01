# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import email
import re
from unittest.mock import patch

import frappe
from frappe.email.doctype.email_account.test_email_account import TestEmailAccount
from frappe.email.doctype.email_queue.email_queue import QueueBuilder
from frappe.tests.utils import FrappeTestCase

test_dependencies = ["Email Account"]


class TestEmail(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Email Unsubscribe")
		frappe.db.delete("Email Queue")
		frappe.db.delete("Email Queue Recipient")

	def test_email_queue(self, send_after=None):
		frappe.sendmail(
			recipients=["test@example.com", "test1@example.com"],
			sender="admin@example.com",
			reference_doctype="User",
			reference_name="Administrator",
			subject="Testing Queue",
			message="This mail is queued!",
			unsubscribe_message="Unsubscribe",
			send_after=send_after,
		)

		email_queue = frappe.db.sql(
			"""select name,message from `tabEmail Queue` where status='Not Sent'""", as_dict=1
		)
		self.assertEqual(len(email_queue), 1)
		queue_recipients = [
			r.recipient
			for r in frappe.db.sql(
				"""SELECT recipient FROM `tabEmail Queue Recipient`
			WHERE status='Not Sent'""",
				as_dict=1,
			)
		]
		self.assertTrue("test@example.com" in queue_recipients)
		self.assertTrue("test1@example.com" in queue_recipients)
		self.assertEqual(len(queue_recipients), 2)
		self.assertTrue("<!--unsubscribe_url-->" in email_queue[0]["message"])

	def test_send_after(self):
		self.test_email_queue(send_after=1)
		from frappe.email.queue import flush

		flush(from_test=True)
		email_queue = frappe.db.sql(
			"""select name from `tabEmail Queue` where status='Sent'""", as_dict=1
		)
		self.assertEqual(len(email_queue), 0)

	def test_flush(self):
		self.test_email_queue()
		from frappe.email.queue import flush

		flush(from_test=True)
		email_queue = frappe.db.sql(
			"""select name from `tabEmail Queue` where status='Sent'""", as_dict=1
		)
		self.assertEqual(len(email_queue), 1)
		queue_recipients = [
			r.recipient
			for r in frappe.db.sql(
				"""select recipient from `tabEmail Queue Recipient`
			where status='Sent'""",
				as_dict=1,
			)
		]
		self.assertTrue("test@example.com" in queue_recipients)
		self.assertTrue("test1@example.com" in queue_recipients)
		self.assertEqual(len(queue_recipients), 2)
		self.assertTrue("Unsubscribe" in frappe.safe_decode(frappe.flags.sent_mail))

	def test_cc_header(self):
		# test if sending with cc's makes it into header
		frappe.sendmail(
			recipients=["test@example.com"],
			cc=["test1@example.com"],
			sender="admin@example.com",
			reference_doctype="User",
			reference_name="Administrator",
			subject="Testing Email Queue",
			message="This is mail is queued!",
			unsubscribe_message="Unsubscribe",
			expose_recipients="header",
		)
		email_queue = frappe.db.sql(
			"""select name from `tabEmail Queue` where status='Not Sent'""", as_dict=1
		)
		self.assertEqual(len(email_queue), 1)
		queue_recipients = [
			r.recipient
			for r in frappe.db.sql(
				"""select recipient from `tabEmail Queue Recipient`
			where status='Not Sent'""",
				as_dict=1,
			)
		]
		self.assertTrue("test@example.com" in queue_recipients)
		self.assertTrue("test1@example.com" in queue_recipients)

		message = frappe.db.sql(
			"""select message from `tabEmail Queue`
			where status='Not Sent'""",
			as_dict=1,
		)[0].message
		self.assertTrue("To: test@example.com" in message)
		self.assertTrue("CC: test1@example.com" in message)

	def test_cc_footer(self):
		frappe.conf.use_ssl = True
		# test if sending with cc's makes it into header
		frappe.sendmail(
			recipients=["test@example.com"],
			cc=["test1@example.com"],
			sender="admin@example.com",
			reference_doctype="User",
			reference_name="Administrator",
			subject="Testing Email Queue",
			message="This is mail is queued!",
			unsubscribe_message="Unsubscribe",
			expose_recipients="footer",
			now=True,
		)
		email_queue = frappe.db.sql(
			"""select name from `tabEmail Queue` where status='Sent'""", as_dict=1
		)
		self.assertEqual(len(email_queue), 1)
		queue_recipients = [
			r.recipient
			for r in frappe.db.sql(
				"""select recipient from `tabEmail Queue Recipient`
			where status='Sent'""",
				as_dict=1,
			)
		]
		self.assertTrue("test@example.com" in queue_recipients)
		self.assertTrue("test1@example.com" in queue_recipients)

		self.assertTrue(
			"This email was sent to test@example.com and copied to test1@example.com"
			in frappe.safe_decode(frappe.flags.sent_mail)
		)

		# check for email tracker
		self.assertTrue("mark_email_as_seen" in frappe.safe_decode(frappe.flags.sent_mail))
		frappe.conf.use_ssl = False

	def test_expose(self):

		from frappe.utils.verified_command import verify_request

		frappe.sendmail(
			recipients=["test@example.com"],
			cc=["test1@example.com"],
			sender="admin@example.com",
			reference_doctype="User",
			reference_name="Administrator",
			subject="Testing Email Queue",
			message="This is mail is queued!",
			unsubscribe_message="Unsubscribe",
			now=True,
		)
		email_queue = frappe.db.sql(
			"""select name from `tabEmail Queue` where status='Sent'""", as_dict=1
		)
		self.assertEqual(len(email_queue), 1)
		queue_recipients = [
			r.recipient
			for r in frappe.db.sql(
				"""select recipient from `tabEmail Queue Recipient`
			where status='Sent'""",
				as_dict=1,
			)
		]
		self.assertTrue("test@example.com" in queue_recipients)
		self.assertTrue("test1@example.com" in queue_recipients)

		message = frappe.db.sql(
			"""select message from `tabEmail Queue`
			where status='Sent'""",
			as_dict=1,
		)[0].message
		self.assertTrue("<!--recipient-->" in message)

		email_obj = email.message_from_string(frappe.safe_decode(frappe.flags.sent_mail))
		for part in email_obj.walk():
			content = part.get_payload(decode=True)

			if content:
				eol = "\r\n"

				frappe.local.flags.signed_query_string = re.search(
					r"(?<=/api/method/frappe.email.queue.unsubscribe\?).*(?=" + eol + ")", content.decode()
				).group(0)
				self.assertTrue(verify_request())
				break

	def test_expired(self):
		self.test_email_queue()
		frappe.db.sql("UPDATE `tabEmail Queue` SET `modified`=(NOW() - INTERVAL '8' day)")

		from frappe.email.queue import set_expiry_for_email_queue

		set_expiry_for_email_queue()

		email_queue = frappe.db.sql(
			"""select name from `tabEmail Queue` where status='Expired'""", as_dict=1
		)
		self.assertEqual(len(email_queue), 1)
		queue_recipients = [
			r.recipient
			for r in frappe.db.sql(
				"""select recipient from `tabEmail Queue Recipient`
			where parent = %s""",
				email_queue[0].name,
				as_dict=1,
			)
		]
		self.assertTrue("test@example.com" in queue_recipients)
		self.assertTrue("test1@example.com" in queue_recipients)
		self.assertEqual(len(queue_recipients), 2)

	def test_sender(self):
		def _patched_assertion(email_account, assertion):
			with patch.object(QueueBuilder, "get_outgoing_email_account", return_value=email_account):
				frappe.sendmail(
					recipients=["test1@example.com"],
					sender="admin@example.com",
					subject="Test Email Queue",
					message="This mail is queued!",
					now=True,
				)
				email_queue_sender = frappe.db.get_value("Email Queue", {"status": "Sent"}, "sender")
				self.assertEqual(email_queue_sender, assertion)

		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
		email_account.default_outgoing = 1

		email_account.always_use_account_name_as_sender_name = 0
		email_account.always_use_account_email_id_as_sender = 0
		_patched_assertion(email_account, "admin@example.com")

		email_account.always_use_account_name_as_sender_name = 1
		_patched_assertion(email_account, "_Test Email Account 1 <admin@example.com>")

		email_account.always_use_account_name_as_sender_name = 0
		email_account.always_use_account_email_id_as_sender = 1
		_patched_assertion(email_account, '"admin@example.com" <test@example.com>')

		email_account.always_use_account_name_as_sender_name = 1
		_patched_assertion(email_account, "_Test Email Account 1 <test@example.com>")

	def test_unsubscribe(self):
		from frappe.email.queue import unsubscribe

		unsubscribe(doctype="User", name="Administrator", email="test@example.com")
		self.assertTrue(
			frappe.db.get_value(
				"Email Unsubscribe",
				{"reference_doctype": "User", "reference_name": "Administrator", "email": "test@example.com"},
			)
		)

		builder = QueueBuilder(
			recipients=["test@example.com", "test1@example.com"],
			sender="admin@example.com",
			reference_doctype="User",
			reference_name="Administrator",
			subject="Testing Email Queue",
			message="This is mail is queued!",
			unsubscribe_message="Unsubscribe",
		)

		# don't send right now
		builder.process()

		email_queue = frappe.db.get_value("Email Queue", {"status": "Not Sent"})
		queue_recipients = [
			r.recipient
			for r in frappe.db.sql(
				"""select recipient from `tabEmail Queue Recipient`
			where status='Not Sent'""",
				as_dict=1,
			)
		]
		self.assertFalse("test@example.com" in queue_recipients)
		self.assertTrue("test1@example.com" in queue_recipients)
		self.assertEqual(len(queue_recipients), 1)

		frappe.get_doc("Email Queue", email_queue).send()
		self.assertTrue("Unsubscribe" in frappe.safe_decode(frappe.flags.sent_mail))

	def test_image_parsing(self):
		import re

		email_account = frappe.get_doc("Email Account", "_Test Email Account 1")

		frappe.db.delete("Communication", {"sender": "sukh@yyy.com"})

		with open(frappe.get_app_path("frappe", "tests", "data", "email_with_image.txt")) as raw:
			messages = {
				'"INBOX"': {"latest_messages": [raw.read()], "seen_status": {2: "UNSEEN"}, "uid_list": [2]}
			}

			email_account = frappe.get_doc("Email Account", "_Test Email Account 1")
			changed_flag = False
			if not email_account.enable_incoming:
				email_account.enable_incoming = True
				changed_flag = True
			mails = TestEmailAccount.mocked_get_inbound_mails(email_account, messages)

			# TODO: fix this flaky test! - 'IndexError: list index out of range' for `.process()` line
			if not mails:
				raise self.skipTest("No inbound mails found / Email Account wasn't patched properly")

			communication = mails[0].process()

		self.assertTrue(
			re.search("""<img[^>]*src=["']/private/files/rtco1.png[^>]*>""", communication.content)
		)
		self.assertTrue(
			re.search("""<img[^>]*src=["']/private/files/rtco2.png[^>]*>""", communication.content)
		)

		if changed_flag:
			email_account.enable_incoming = False


class TestVerifiedRequests(FrappeTestCase):
	def test_round_trip(self):
		from frappe.utils import set_request
		from frappe.utils.verified_command import get_signed_params, verify_request

		test_cases = [{"xyz": "abc"}, {"email": "a@b.com", "user": "xyz"}]

		for params in test_cases:
			signed_url = get_signed_params(params)
			set_request(method="GET", path="?" + signed_url)
			self.assertTrue(verify_request())
		frappe.local.request = None
