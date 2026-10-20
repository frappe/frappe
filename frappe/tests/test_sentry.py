import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import sentry_sdk
from sentry_sdk.transport import Transport
from werkzeug.wrappers import Request

import frappe
from frappe.tests import UnitTestCase
from frappe.utils.sentry import capture_exception, set_scope

LOGIN_BODY = {"usr": "test@example.com", "pwd": "pw-1"}


class TestSentryScope(UnitTestCase):
	def test_aware_enqueued_at(self):
		enqueued_at = datetime(2026, 5, 18, 12, 0, tzinfo=UTC)
		now = enqueued_at + timedelta(seconds=45)

		self.assert_job_context(enqueued_at, now, wait=45)

	def test_naive_enqueued_at(self):
		enqueued_at = datetime(2026, 5, 18, 12, 0)
		now = enqueued_at.replace(tzinfo=UTC) + timedelta(seconds=45)

		self.assert_job_context(enqueued_at, now, wait=45)

	def assert_job_context(self, enqueued_at, now, wait):
		job = MagicMock()
		job._kwargs = {"method": "frappe.ping"}
		job.id = "test-job-id"
		job.enqueued_at = enqueued_at

		scope = MagicMock()
		with (
			patch("frappe.utils.sentry.rq.get_current_job", return_value=job),
			patch("frappe.utils.sentry.datetime") as datetime_mock,
		):
			datetime_mock.now.return_value = now
			set_scope(scope)

		datetime_mock.now.assert_called_once_with(UTC)
		scope.set_transaction_name.assert_called_once_with("frappe.ping")
		scope.set_extra.assert_called_once()
		self.assertEqual("job", scope.set_extra.call_args.args[0])

		context = scope.set_extra.call_args.args[1]
		self.assertEqual("test-job-id", context.uuid)
		self.assertEqual(wait, context.wait)
		self.assertEqual(job._kwargs, context.kwargs)


class TestSentryRequestBody(UnitTestCase):
	def test_sanitize_body_masks_nested_and_json_string_values(self):
		from frappe.utils.sentry import sanitize_body

		body = {
			"usr": "test@example.com",
			"doc": json.dumps(
				{"doctype": "Email Account", "password": "pw-1", "rows": [{"api_secret": "pw-2"}]}
			),
		}
		cleaned = sanitize_body(body)

		self.assertEqual(cleaned["usr"], "test@example.com")
		self.assertNotIn("pw-1", json.dumps(cleaned))
		self.assertNotIn("pw-2", json.dumps(cleaned))

	def test_captured_event_has_no_request_secrets(self):
		sent = []

		class RecordingTransport(Transport):
			def capture_envelope(self, envelope):
				sent.extend(item.payload.json for item in envelope.items if item.payload.json)

		client = sentry_sdk.Client(dsn="https://key@example.com/1", transport=RecordingTransport)
		frappe.local.request = Request.from_values("/api/method/login", method="POST", json=LOGIN_BODY)
		self.addCleanup(setattr, frappe.local, "request", None)

		with (
			patch("frappe.get_system_settings", return_value=1),
			sentry_sdk.new_scope() as scope,
		):
			scope.set_client(client)
			try:
				raise RuntimeError("test error")
			except RuntimeError:
				capture_exception()
			client.flush()

		self.assertEqual(len(sent), 1)
		self.assertNotIn("pw-1", json.dumps(sent))
		self.assertIn("test@example.com", json.dumps(sent))
