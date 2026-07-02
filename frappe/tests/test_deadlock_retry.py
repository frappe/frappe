# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
import frappe.app as app
from frappe.tests import UnitTestCase


class FakeDB:
	def __init__(self):
		self.commit_count = 0
		self.rollbacks = 0

	def rollback(self):
		self.rollbacks += 1


class TestDeadlockRetry(UnitTestCase):
	"""retry_deadlocks: transient deadlocks replay, non-replayable attempts don't."""

	def setUp(self):
		self.db = FakeDB()
		self.patchers = [
			patch.object(frappe, "db", self.db),
			patch.object(app, "time", MagicMock()),
			patch.object(frappe, "logger", MagicMock(return_value=MagicMock())),
		]
		for patcher in self.patchers:
			patcher.start()
		frappe.local.flags = frappe._dict()
		app.reset_response_state()

	def tearDown(self):
		for patcher in self.patchers:
			patcher.stop()

	def _run(self, fail_times=1, during_attempt=None, mimetype="application/json"):
		request = SimpleNamespace(method="POST", path="/api/method/test", mimetype=mimetype)
		calls = 0

		@app.retry_deadlocks
		def dispatch(request):
			nonlocal calls
			calls += 1
			if during_attempt:
				during_attempt()
			if calls <= fail_times:
				raise frappe.QueryDeadlockError("deadlock")
			return "ok"

		try:
			return dispatch(request), calls
		except frappe.QueryDeadlockError:
			return None, calls

	def test_retries_transient_deadlock(self):
		result, calls = self._run(fail_times=app.MAX_DEADLOCK_RETRIES)
		self.assertEqual(result, "ok")
		self.assertEqual(calls, app.MAX_DEADLOCK_RETRIES + 1)
		self.assertEqual(self.db.rollbacks, app.MAX_DEADLOCK_RETRIES)

	def test_gives_up_after_max_retries(self):
		result, calls = self._run(fail_times=app.MAX_DEADLOCK_RETRIES + 1)
		self.assertIsNone(result)
		self.assertEqual(calls, app.MAX_DEADLOCK_RETRIES + 1)

	def test_no_replay_after_commit(self):
		def commit():
			self.db.commit_count += 1

		result, calls = self._run(during_attempt=commit)
		self.assertIsNone(result)
		self.assertEqual(calls, 1)
		self.assertEqual(self.db.rollbacks, 0)

	def test_no_replay_after_enqueue(self):
		def enqueue():
			frappe.local.flags.enqueued_jobs = (frappe.local.flags.enqueued_jobs or 0) + 1

		result, calls = self._run(during_attempt=enqueue)
		self.assertIsNone(result)
		self.assertEqual(calls, 1)

	def test_no_replay_for_multipart(self):
		result, calls = self._run(mimetype="multipart/form-data")
		self.assertIsNone(result)
		self.assertEqual(calls, 1)

	def test_response_state_reset_between_attempts(self):
		seen_logs = []

		def dirty_response():
			seen_logs.append(list(frappe.local.message_log))
			frappe.local.message_log.append("leftover")

		result, _calls = self._run(fail_times=1, during_attempt=dirty_response)
		self.assertEqual(result, "ok")
		self.assertEqual(seen_logs, [[], []])
