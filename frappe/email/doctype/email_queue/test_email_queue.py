# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import textwrap

import frappe
from frappe.email.doctype.email_queue.email_queue import SendMailContext, get_email_retry_limit
from frappe.tests import IntegrationTestCase


class TestEmailQueue(IntegrationTestCase):
	def setUp(self):
		# set default outgoing email account for tests
		frappe.db.set_value("Email Account", "_Test Email Account 1", "default_outgoing", 1)
		# clean up any test email queues
		test_emails = [f"to{i}@example.com" for i in range(200)] + ["cc@example.com", "bcc@example.com"]
		frappe.db.delete("Email Queue Recipient", {"recipient": ["in", test_emails]})

		# clean up any cc and bcc recipients created by tests
		test_cc_emails = [f"cc{i}@example.com" for i in range(10)]
		test_bcc_emails = [f"bcc{i}@example.com" for i in range(10)]
		frappe.db.delete("Email Queue Recipient", {"recipient": ["in", test_cc_emails + test_bcc_emails]})

	def test_email_queue_deletion_based_on_modified_date(self):
		from frappe.email.doctype.email_queue.email_queue import EmailQueue

		old_record = frappe.get_doc(
			{
				"doctype": "Email Queue",
				"sender": "Test <test@example.com>",
				"show_as_cc": "",
				"message": "Test message",
				"status": "Sent",
				"priority": 1,
				"recipients": [
					{
						"recipient": "test_auth@test.com",
					}
				],
			}
		).insert()

		old_record.creation = "2010-01-01 00:00:01"
		old_record.recipients[0].creation = old_record.creation
		old_record.db_update_all()

		new_record = frappe.copy_doc(old_record)
		new_record.insert()

		EmailQueue.clear_old_logs()

		self.assertFalse(frappe.db.exists("Email Queue", old_record.name))
		self.assertFalse(frappe.db.exists("Email Queue Recipient", {"parent": old_record.name}))

		self.assertTrue(frappe.db.exists("Email Queue", new_record.name))
		self.assertTrue(frappe.db.exists("Email Queue Recipient", {"parent": new_record.name}))

	def test_failed_email_notification(self):
		subject = frappe.generate_hash()
		email_record = frappe.new_doc("Email Queue")
		email_record.sender = "Test <test@example.com>"
		email_record.message = textwrap.dedent(
			f"""\
		MIME-Version: 1.0
		Message-Id: {frappe.generate_hash()}
		X-Original-From: Test <test@example.com>
		Subject: {subject}
		From: Test <test@example.com>
		To: <!--recipient-->
		Date: {frappe.utils.now_datetime().strftime("%a, %d %b %Y %H:%M:%S %z")}
		Reply-To: test@example.com
		X-Frappe-Site: {frappe.local.site}
		"""
		)
		email_record.status = "Error"
		email_record.retry = get_email_retry_limit()
		email_record.priority = 1
		email_record.reference_doctype = "User"
		email_record.reference_name = "Administrator"
		email_record.insert()

		# Simulate an exception so that we get a notification
		try:
			with SendMailContext(queue_doc=email_record):
				raise Exception("Test Exception")
		except Exception:
			pass

		notification_log = frappe.db.get_value(
			"Notification Log",
			{"subject": f"Failed to send email with subject: {subject}"},
		)
		self.assertTrue(notification_log)

	def test_perf_reusing_smtp_server(self):
		"""Ensure that same smtpserver instance is being returned when retrieved multiple times."""

		self.assertTrue(frappe.new_doc("Email Queue").get_email_account()._from_site_config)

		def get_server(q):
			return q.get_email_account().get_smtp_server()

		self.assertIs(get_server(frappe.new_doc("Email Queue")), get_server(frappe.new_doc("Email Queue")))

		q1 = frappe.new_doc("Email Queue", email_account="_Test Email Account 1")
		q2 = frappe.new_doc("Email Queue", email_account="_Test Email Account 1")
		self.assertIsNot(get_server(frappe.new_doc("Email Queue")), get_server(q1))
		self.assertIs(get_server(q1), get_server(q2))

	def test_queue_separately_cc_and_bcc_receives_single_email(self):
		"""Test that CC and BCC recipients receive only one email when queue_separately=True"""
		from frappe.email.doctype.email_queue.email_queue import QueueBuilder

		to_recipients = ["to1@example.com", "to2@example.com", "to3@example.com"]
		cc_recipients = ["cc1@example.com", "cc2@example.com"]
		bcc_recipients = ["bcc1@example.com", "bcc2@example.com"]

		builder = QueueBuilder(
			recipients=to_recipients,
			sender="sender@example.com",
			subject="Test Subject",
			message="Test Message",
			cc=cc_recipients,
			bcc=bcc_recipients,
			queue_separately=True,
		)

		builder.process(send_now=False)

		# verify each CC receives exactly one email
		for cc_email in cc_recipients:
			count = frappe.db.count("Email Queue Recipient", filters={"recipient": cc_email})
			self.assertEqual(count, 1, f"CC {cc_email} should receive exactly 1 email")

			# verify each BCC receives exactly one email
		for bcc_email in bcc_recipients:
			count = frappe.db.count("Email Queue Recipient", filters={"recipient": bcc_email})
			self.assertEqual(count, 1, f"BCC {bcc_email} should receive exactly 1 email")

			# verify each TO receives exactly one email
		for to_email in to_recipients:
			count = frappe.db.count("Email Queue Recipient", filters={"recipient": to_email})
			self.assertEqual(count, 1, f"TO {to_email} should receive exactly 1 email")

	def test_queue_separately_with_large_recipient_list(self):
		"""Test that CC/BCC receive single email even with batched TO recipients (>100)"""
		from unittest.mock import patch

		from frappe.email.doctype.email_queue.email_queue import QueueBuilder

		# generate 150 TO recipients to trigger queue_separately (>100 threshold)
		to_recipients = [f"to{i}@example.com" for i in range(150)]
		cc_recipient = "cc@example.com"

		builder = QueueBuilder(
			recipients=to_recipients,
			sender="sender@example.com",
			subject="Test Subject",
			message="Test Message",
			cc=[cc_recipient],
			queue_separately=True,
		)

		builder.process(send_now=False)

		# CC should still only appear once
		cc_queue_count = frappe.db.count("Email Queue Recipient", filters={"recipient": cc_recipient})
		self.assertEqual(
			cc_queue_count,
			1,
			f"CC recipient should receive exactly 1 email even with batching, got {cc_queue_count}",
		)
