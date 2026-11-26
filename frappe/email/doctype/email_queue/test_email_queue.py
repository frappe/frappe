# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import re
import smtplib
import textwrap
from email import message_from_bytes, message_from_string
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

import frappe
from frappe.email.doctype.email_queue.email_queue import SendMailContext, get_email_retry_limit
from frappe.tests.utils import FrappeTestCase, change_settings


class TestEmailQueue(FrappeTestCase):
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

		old_record.modified = "2010-01-01 00:00:01"
		old_record.recipients[0].modified = old_record.modified
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

	def test_redacts_message_only_once_sent(self):
		"""A failed send must keep the message intact, it is the only copy the retry has."""
		link = f"http://example.com/update-password?key={frappe.generate_hash()}"
		email_record = frappe.new_doc(
			"Email Queue",
			sender="Test <test@example.com>",
			show_as_cc="",
			email_account="_Test Email Account 1",
			message=textwrap.dedent(
				f"""\
			MIME-Version: 1.0
			Content-Type: text/plain; charset="utf-8"
			Message-Id: {frappe.generate_hash()}
			Subject: Welcome
			From: Test <test@example.com>
			To: <!--recipient-->

			Hello, complete your registration at {link}
			"""
			),
			status="Not Sent",
			priority=1,
			redact_message_after_send=1,
			recipients=[{"recipient": "test_redact@example.com"}],
		).insert()

		mock_session = MagicMock()
		mock_session.has_extn.return_value = False
		mock_session.sendmail.side_effect = smtplib.SMTPRecipientsRefused(
			{"test_redact@example.com": (450, b"Mailbox busy")}
		)
		mock_smtp_server = MagicMock()
		mock_smtp_server.session = mock_session

		frappe.flags.testing_email = True
		try:
			with self.assertRaises(smtplib.SMTPRecipientsRefused):
				email_record.send(smtp_server_instance=mock_smtp_server)

			self.assertIn(link, frappe.db.get_value("Email Queue", email_record.name, "message"))

			mock_session.sendmail.side_effect = None
			email_record.reload()
			email_record.send(smtp_server_instance=mock_smtp_server)
		finally:
			frappe.flags.testing_email = False

		self.assertIn(link, mock_session.sendmail.call_args.kwargs["msg"].decode())
		self.assertNotIn(link, frappe.db.get_value("Email Queue", email_record.name, "message"))

	def test_notification_keeps_large_recipient_list_in_one_queue(self):
		recipients = [f"notify{index}@example.com" for index in range(101)]

		queue = frappe.sendmail(
			recipients=recipients, subject="Notification", message="Body", is_notification=True
		)

		self.assertCountEqual([row.recipient for row in queue.recipients], recipients)

	def test_reply_to_removed_only_from_copy_sent_to_that_address(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		queue = frappe.sendmail(
			recipients=["customer@example.com"],
			cc=["manager@example.com"],
			reply_to="manager@example.com",
			subject="Reply-To",
			message="Test message",
		)
		context = SendMailContext(queue)

		manager_copy = message_from_bytes(context.build_message("manager@example.com"))
		customer_copy = message_from_bytes(context.build_message("customer@example.com"))

		self.assertIsNone(manager_copy["Reply-To"])
		self.assertEqual(customer_copy["Reply-To"], "manager@example.com")

	def test_message_without_attachments_has_alternative_root(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		queue = frappe.sendmail(
			recipients=["customer@example.com"],
			cc=["manager@example.com"],
			reply_to="support@example.com",
			subject="No Attachments",
			message="Test message",
		)
		queued = message_from_string(queue.message)
		message = message_from_bytes(SendMailContext(queue).build_message("customer@example.com"))

		self.assertEqual(
			[part.get_content_type() for part in message.walk()],
			["multipart/alternative", "text/plain", "text/html"],
		)
		self.assertEqual(len(message.get_all("Content-Type")), 1)
		self.assertEqual(len(message.get_all("MIME-Version")), 1)
		for header in ("From", "To", "CC", "Subject", "Reply-To", "Message-Id", "Date", "X-Frappe-Site"):
			self.assertEqual(
				message[header], queued[header].replace("<!--recipient-->", "customer@example.com")
			)

	def test_message_with_inline_image_has_alternative_root(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		queue = frappe.sendmail(
			recipients=["customer@example.com"],
			subject="Inline Image",
			message='<img embed="files/logo.png">',
			inline_images=[{"filename": "files/logo.png", "filecontent": b"image"}],
		)
		message = message_from_bytes(SendMailContext(queue).build_message("customer@example.com"))

		self.assertEqual(
			[part.get_content_type() for part in message.walk()],
			["multipart/alternative", "text/plain", "multipart/related", "text/html", "image/png"],
		)

	def test_message_with_attachment_keeps_mixed_root(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		file = frappe.get_doc(doctype="File", file_name="queued.txt", content="queued", is_private=1).insert()
		self.addCleanup(file.delete)
		for attachment in ({"fname": "embedded.txt", "fcontent": "embedded"}, {"fid": file.name}):
			with self.subTest(attachment=attachment):
				queue = frappe.sendmail(
					recipients=["customer@example.com"],
					subject="Attachment",
					message="Test message",
					attachments=[attachment],
				)
				message = message_from_bytes(SendMailContext(queue).build_message("customer@example.com"))

				self.assertEqual(
					[part.get_content_type() for part in message.walk()],
					["multipart/mixed", "multipart/alternative", "text/plain", "text/html", "text/plain"],
				)

	def test_plain_text_part_has_urls_of_html_part(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		unsubscribe = {
			"reference_doctype": "User",
			"reference_name": "Administrator",
			"unsubscribe_message": "Unsubscribe",
		}
		body_links = (
			'<p>Read <a href="https://example.com/docs">the docs</a>.</p>'
			'<p><a href="https://example.com/raw">https://example.com/raw</a></p>'
			'<p><a href="mailto:jane@example.com">jane@example.com</a></p>'
		)
		for case, kwargs, url_count in (
			("no URLs", {}, 0),
			("masthead", {"brand_name": "Example"}, 1),
			("brand logo", {"brand_logo": "https://example.com/logo.png"}, 2),
			("body links", {"message": body_links}, 2),
			("unsubscribe link", unsubscribe, 1),
			("tracker", {"email_read_tracker_url": "/api/method/frappe.ping"}, 1),
			(
				"all",
				{
					"brand_name": "Example",
					"brand_logo": "https://example.com/logo.png",
					"message": body_links,
					"email_read_tracker_url": "/api/method/frappe.ping",
					**unsubscribe,
				},
				6,
			),
		):
			with self.subTest(case=case):
				text, html = self.get_sent_parts(**kwargs)
				soup = BeautifulSoup(html, "html.parser")
				html_urls = [link["href"] for link in soup.find_all("a", href=re.compile("^https?://"))]
				html_urls += [image["src"] for image in soup.find_all("img", src=re.compile("^https?://"))]

				self.assertEqual(len(html_urls), url_count)
				self.assertCountEqual(re.findall(r"https?://[^\s()]+", text), html_urls)
				self.assertNotIn("<!--", text)

	def test_plain_text_part_has_words_of_html_part(self):
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(
			frappe.db.set_default, "email_footer_address", frappe.db.get_default("email_footer_address")
		)
		frappe.db.set_default("email_footer_address", "Example Technologies\nMumbai, India")
		frappe.set_user("test@example.com")

		text, html = self.get_sent_parts(
			brand_name="Example", header=["Assignment Update", "blue"], message="<p>Your task is due.</p>"
		)
		html_words = BeautifulSoup(html, "html.parser").body.get_text(" ").split()

		self.assertIn("Mumbai,", html_words)
		self.assertEqual([word for word in text.split() if "://" not in word], html_words)

	def get_sent_parts(self, brand_name=None, brand_logo=None, message="<p>Hello</p>", **kwargs):
		"""Return the decoded plain-text and HTML parts of a message sent to customer@example.com."""
		with (
			patch("frappe.email.email_body.get_brand_name", return_value=brand_name),
			patch("frappe.email.email_body.get_brand_logo", return_value=brand_logo),
		):
			queue = frappe.sendmail(
				recipients=["customer@example.com"],
				subject="Parts",
				message=message,
				with_container=True,
				**kwargs,
			)
		message = message_from_bytes(SendMailContext(queue).build_message("customer@example.com"))
		return [part.get_payload(decode=True).decode() for part in message.get_payload()]

	def test_reply_to_address_matching(self):
		for reply_to, recipient, is_kept in (
			("Manager <Manager@Example.com>", "manager@example.com", False),
			("manager@example.com", "Manager <MANAGER@example.com>", False),
			("manager@example.com, other@example.com", "manager@example.com", True),
			("manager@example.com", "other@example.com", True),
		):
			with self.subTest(reply_to=reply_to, recipient=recipient):
				queue = frappe.new_doc(
					"Email Queue",
					message=f"From: test@example.com\nTo: <!--recipient-->\nReply-To: {reply_to}\n\nBody\n",
				)
				copy = message_from_bytes(SendMailContext(queue).build_message(recipient))
				self.assertEqual(copy["Reply-To"], reply_to if is_kept else None)

	@change_settings("System Settings", store_attached_pdf_document=0)
	def test_print_attachment_renders_once_for_every_recipient(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		email_record = frappe.sendmail(
			recipients=["test_to@example.com"],
			cc=["test_cc@example.com"],
			bcc=["test_bcc@example.com"],
			subject="Print attachment",
			message="Test message",
			attachments=[{"print_format_attachment": 1, "doctype": "User", "name": "test@example.com"}],
		)

		with patch(
			"frappe.attach_print", return_value={"fname": "test.pdf", "fcontent": b"%PDF"}
		) as attach_print:
			email_record.send()

		attach_print.assert_called_once()
		self.assertIn(b'filename="test.pdf"', frappe.flags.sent_mail)
