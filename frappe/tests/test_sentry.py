import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import sentry_sdk
from sentry_sdk.transport import Transport
from werkzeug.wrappers import Request

import frappe
from frappe.tests import UnitTestCase
from frappe.utils.sentry import before_send, capture_exception, set_scope

LOGIN_BODY = {"usr": "test@example.com", "pwd": "pw-1"}
DOC_PASSWORD = "pw-4"
QUERY_PASSWORD = "pw-3"
SECRET_DOC = json.dumps({"doctype": "Email Account", "password": DOC_PASSWORD})
# Built from a name so the secrets don't sit in frame locals of the failing code, which Sentry captures.
REQUESTS = {
	"login": lambda: Request.from_values("/api/method/login", method="POST", json=LOGIN_BODY),
	"query": lambda: Request.from_values("/api/method/ping?pwd=" + QUERY_PASSWORD + "&cmd=ping"),
}


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

	def test_sanitize_body_handles_deep_nesting(self):
		from frappe.utils.sentry import sanitize_body

		depth = 500
		deep = "[" * depth + "]" * depth
		self.assertEqual(sanitize_body({"doc": deep, "usr": "test@example.com"})["usr"], "test@example.com")
		self.assertIn("********", json.dumps(sanitize_body(deep)))

	def test_secret_key_match_ignores_case(self):
		from frappe.utils.logger import sanitized_dict

		masked = sanitized_dict({"Password": "pw-1", "apiKey": "pw-2", "clientSecret": "pw-3", "usr": "u"})
		self.assertEqual(
			masked, {"Password": "********", "apiKey": "********", "clientSecret": "********", "usr": "u"}
		)

	def test_captured_event_has_no_request_secrets(self):
		sent = self.capture_error_event("login")

		self.assertEqual(len(sent), 1)
		self.assertNotIn("pw-1", json.dumps(sent))
		self.assertIn("test@example.com", json.dumps(sent))

	def test_captured_event_masks_frame_vars_and_query_string(self):
		sent = self.capture_error_event("query", doc=SECRET_DOC)

		payload = json.dumps(sent)
		self.assertNotIn(QUERY_PASSWORD, payload)
		self.assertNotIn(DOC_PASSWORD, payload)
		self.assertIn("cmd=ping", payload)
		self.assertIn("Email Account", payload)

	def test_message_event_masks_frame_vars(self):
		sent = self.capture_error_event("query", doc=SECRET_DOC, as_message=True)

		self.assertEqual(len(sent), 1)
		self.assertIn("threads", sent[0])
		self.assertNotIn(DOC_PASSWORD, json.dumps(sent))
		self.assertIn("Email Account", json.dumps(sent))

	def capture_error_event(self, request_name, doc=None, as_message=False):
		sent = []

		class RecordingTransport(Transport):
			def capture_envelope(self, envelope):
				sent.extend(item.payload.json for item in envelope.items if item.payload.json)

		client = sentry_sdk.Client(
			dsn="https://key@example.com/1",
			transport=RecordingTransport,
			before_send=before_send,
			attach_stacktrace=True,
		)
		frappe.local.request = REQUESTS[request_name]()
		self.addCleanup(setattr, frappe.local, "request", None)

		with (
			patch("frappe.get_system_settings", return_value=1),
			sentry_sdk.new_scope() as scope,
		):
			scope.set_client(client)
			if as_message:
				log_message(doc)
			else:
				try:
					raise_error(doc)
				except RuntimeError:
					capture_exception()
			client.flush()

		return sent


def raise_error(doc):
	raise RuntimeError("test error")


def log_message(doc):
	capture_exception("test message")
