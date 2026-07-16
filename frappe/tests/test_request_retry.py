# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests.test_api import FrappeAPITestCase
from frappe.tests.utils import whitelist_for_tests

calls = {"flaky": 0, "after_commit": 0}


@whitelist_for_tests(allow_guest=True)
def flaky_method():
	calls["flaky"] += 1
	if calls["flaky"] == 1:
		raise frappe.QueryDeadlockError("simulated transaction conflict")
	return "ok"


@whitelist_for_tests(allow_guest=True)
def conflict_after_commit():
	calls["after_commit"] += 1
	# the mid-request commit is the point: it must disable the replay
	frappe.db.commit()  # nosemgrep
	raise frappe.QueryDeadlockError("simulated conflict after commit")


class TestTransactionConflictRetry(FrappeAPITestCase):
	def test_conflicted_request_is_replayed(self):
		calls["flaky"] = 0
		response = self.get(self.method(f"{__name__}.flaky_method"))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(calls["flaky"], 2)

	def test_no_replay_after_mid_request_commit(self):
		calls["after_commit"] = 0
		response = self.get(self.method(f"{__name__}.conflict_after_commit"))
		self.assertNotEqual(response.status_code, 200)
		self.assertEqual(calls["after_commit"], 1)
