# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import unittest
from unittest.mock import patch

import frappe
import frappe.app as app


class FakeRequest:
	def __init__(self, method):
		self.method = method


class TestDeadlockRetry(unittest.TestCase):
	"""retry_deadlocks: writes retry on deadlock, reads don't."""

	def _run(self, method, fail_times):
		calls = {"n": 0}
		sleeps = []

		@app.retry_deadlocks
		def dispatch(request):
			if calls["n"] < fail_times:
				calls["n"] += 1
				raise frappe.QueryDeadlockError("deadlock")
			return "ok"

		with patch.object(app.time, "sleep", sleeps.append):
			result = dispatch(FakeRequest(method))
		return result, calls["n"], sleeps

	def test_write_succeeds_after_retries(self):
		result, attempts, sleeps = self._run("POST", fail_times=app.MAX_DEADLOCK_RETRIES)
		self.assertEqual(result, "ok")
		self.assertEqual(attempts, app.MAX_DEADLOCK_RETRIES)
		self.assertEqual(len(sleeps), app.MAX_DEADLOCK_RETRIES)

	def test_write_gives_up_after_max(self):
		with self.assertRaises(frappe.QueryDeadlockError):
			self._run("POST", fail_times=app.MAX_DEADLOCK_RETRIES + 1)

	def test_read_not_retried(self):
		with self.assertRaises(frappe.QueryDeadlockError):
			self._run("GET", fail_times=1)


if __name__ == "__main__":
	unittest.main()
