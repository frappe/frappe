from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from frappe.tests import UnitTestCase
from frappe.utils.sentry import set_scope


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
