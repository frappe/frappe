# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import smtplib
import textwrap
import time
from unittest.mock import MagicMock, patch

import frappe
from frappe.email.doctype.email_queue.email_queue import (
	EmailRateLimiter,
	SendMailContext,
	get_email_retry_limit,
)
from frappe.tests import IntegrationTestCase


class TestEmailQueue(IntegrationTestCase):
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

	def test_discards_smtp_session_on_send_failure(self):
		"""SMTPRecipientsRefused (not an SMTPResponseException) must still discard the session."""
		email_record = frappe.new_doc(
			"Email Queue",
			sender="Test <test@example.com>",
			show_as_cc="",
			message="Test message",
			status="Not Sent",
			priority=1,
			recipients=[{"recipient": "test_refused@example.com"}],
		).insert()

		mock_session = MagicMock()
		mock_session.has_extn.return_value = False
		mock_session.sendmail.side_effect = smtplib.SMTPRecipientsRefused(
			{"test_refused@example.com": (550, b"Mailbox unavailable")}
		)
		mock_smtp_server = MagicMock()
		mock_smtp_server.session = mock_session

		frappe.flags.testing_email = True
		try:
			with self.assertRaises(smtplib.SMTPRecipientsRefused):
				email_record.send(smtp_server_instance=mock_smtp_server)
		finally:
			frappe.flags.testing_email = False

		mock_smtp_server.discard_session.assert_called_once()

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


class TestEmailQueueRateLimit(IntegrationTestCase):
	EMAIL_ACCOUNT = "_Test Email Account 1"

	def setUp(self):
		self._clear_counters()
		self.addCleanup(self._clear_counters)
		# Sending commits (Email Queue status updates), which also persists the
		# limits set by a test, so the reset has to be committed too.
		self.addCleanup(self._set_limits, commit=True)

	@staticmethod
	def _clear_counters():
		frappe.cache.delete_keys("email-send-rate-limit:")

	def _set_limits(self, per_minute=0, per_hour=0, per_day=0, commit=False):
		frappe.get_doc("Email Account", self.EMAIL_ACCOUNT).db_set(
			{
				"send_rate_limit_per_minute": per_minute,
				"send_rate_limit_per_hour": per_hour,
				"send_rate_limit_per_day": per_day,
			},
			commit=commit,
		)

	@staticmethod
	def _delete_queue(name):
		# Sending commits, so rows would otherwise outlive the test's rollback.
		frappe.db.delete("Email Queue Recipient", {"parent": name})
		frappe.db.delete("Email Queue", {"name": name})
		frappe.db.commit()  # nosemgrep

	def _make_queue(self, recipients):
		queue = frappe.new_doc(
			"Email Queue",
			sender="Test <test@example.com>",
			show_as_cc="",
			email_account=self.EMAIL_ACCOUNT,
			message=textwrap.dedent(
				f"""\
			MIME-Version: 1.0
			Content-Type: text/plain; charset="utf-8"
			Message-Id: {frappe.generate_hash()}
			Subject: Rate limit
			From: Test <test@example.com>
			To: <!--recipient-->

			Hello
			"""
			),
			status="Not Sent",
			# Ahead of any other queued mail, so flush() reaches these first.
			priority=100,
			recipients=[{"recipient": r} for r in recipients],
		).insert()
		self.addCleanup(self._delete_queue, queue.name)
		return queue

	@staticmethod
	def _mock_smtp_server():
		mock_session = MagicMock()
		mock_session.has_extn.return_value = False
		mock_smtp_server = MagicMock()
		mock_smtp_server.session = mock_session
		return mock_smtp_server

	def test_limiter_disabled_without_limits(self):
		self._set_limits()
		limiter = EmailRateLimiter(frappe.get_cached_doc("Email Account", self.EMAIL_ACCOUNT))
		self.assertFalse(limiter.enabled)
		self.assertTrue(all(limiter.acquire() for _ in range(50)))

	def test_limiter_enforces_tightest_window_without_leaking_slots(self):
		self._set_limits(per_minute=5, per_hour=3)
		limiter = EmailRateLimiter(frappe.get_cached_doc("Email Account", self.EMAIL_ACCOUNT))

		self.assertEqual([limiter.acquire() for _ in range(4)], [True, True, True, False])
		self.assertFalse(limiter.has_capacity())

		# A rejected acquire must not consume a slot in the other windows.
		self._set_limits(per_minute=5)
		limiter = EmailRateLimiter(frappe.get_cached_doc("Email Account", self.EMAIL_ACCOUNT))
		self.assertEqual([limiter.acquire() for _ in range(3)], [True, True, False])

	def test_limit_reached_is_logged_once_per_window(self):
		self._set_limits(per_minute=1)
		limiter = EmailRateLimiter(frappe.get_cached_doc("Email Account", self.EMAIL_ACCOUNT))
		window_start = (int(time.time()) // 60) * 60

		with patch("frappe.logger") as logger, patch("time.time", return_value=window_start + 1):
			self.assertTrue(limiter.acquire())
			self.assertFalse(limiter.acquire())
			self.assertFalse(limiter.acquire())
			self.assertFalse(limiter.has_capacity())

			logger.assert_called_once_with("email_rate_limit")
			logger.return_value.info.assert_called_once()
			message = logger.return_value.info.call_args.args[0]
			self.assertIn(self.EMAIL_ACCOUNT, message)
			self.assertIn("per-minute send limit (1)", message)

		# The next window starts fresh and is logged again once exhausted.
		with patch("frappe.logger") as logger, patch("time.time", return_value=window_start + 61):
			self.assertTrue(limiter.acquire())
			self.assertFalse(limiter.acquire())
			self.assertFalse(limiter.acquire())
			logger.return_value.info.assert_called_once()

	def test_rate_limited_queue_is_deferred_without_using_retries(self):
		self._set_limits(per_minute=2)
		email_record = self._make_queue([f"rate_limit_{i}@example.com" for i in range(3)])
		smtp_server = self._mock_smtp_server()

		frappe.flags.testing_email = True
		try:
			email_record.send(smtp_server_instance=smtp_server)
			self.assertEqual(smtp_server.session.sendmail.call_count, 2)
			self.assertEqual(email_record.flags.rate_limited_account, self.EMAIL_ACCOUNT)

			email_record.reload()
			self.assertEqual(email_record.status, "Partially Sent")
			self.assertEqual(email_record.retry, 0)
			self.assertEqual([r.status for r in email_record.recipients], ["Sent", "Sent", "Not Sent"])

			# Still within the same window: nothing is sent and the status isn't touched.
			email_record.send(smtp_server_instance=smtp_server)
			self.assertEqual(smtp_server.session.sendmail.call_count, 2)
			self.assertEqual(
				frappe.db.get_value("Email Queue", email_record.name, "status"), "Partially Sent"
			)

			# Window resets: the remaining recipient goes out.
			self._clear_counters()
			email_record.reload()
			email_record.send(smtp_server_instance=smtp_server)
		finally:
			frappe.flags.testing_email = False

		self.assertEqual(smtp_server.session.sendmail.call_count, 3)
		self.assertEqual(frappe.db.get_value("Email Queue", email_record.name, "status"), "Sent")

	def test_flush_holds_back_queues_of_rate_limited_account(self):
		from frappe.email.queue import flush
		from frappe.utils import add_to_date, now_datetime

		self._set_limits(per_hour=1)
		queues = [
			self._make_queue(["rate_limit_first@example.com"]),
			self._make_queue(["rate_limit_second@example.com"]),
		]

		with self.freeze_time(add_to_date(now_datetime(), seconds=12)):
			flush()

		rows = frappe.get_all(
			"Email Queue",
			filters={"name": ("in", [q.name for q in queues])},
			fields=["status", "retry"],
		)
		self.assertEqual(sorted(r.status for r in rows), ["Not Sent", "Sent"])
		self.assertTrue(all(r.retry == 0 for r in rows))
