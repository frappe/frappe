# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.core.doctype.system_settings.system_settings import load
from frappe.tests import IntegrationTestCase


class TestSystemSettings(IntegrationTestCase):
	def test_load_returns_saved_value_over_stale_default(self):
		self.addCleanup(
			frappe.db.set_single_value,
			"System Settings",
			"time_zone",
			frappe.db.get_single_value("System Settings", "time_zone"),
		)
		self.addCleanup(frappe.db.set_default, "time_zone", frappe.db.get_default("time_zone"))

		frappe.db.set_single_value("System Settings", "time_zone", "Australia/Brisbane")
		frappe.db.set_default("time_zone", "Australia/Adelaide")

		with self.set_user("test@example.com"):
			self.assertEqual(load()["defaults"]["time_zone"], "Australia/Brisbane")

	def test_submission_queue_timeout_cannot_be_more_than_one_hour(self):
		with self.set_user("test@example.com"):
			settings = frappe.get_doc("System Settings")
			settings.submission_queue_timeout = 3601
			self.assertRaises(frappe.ValidationError, settings.save)

	@IntegrationTestCase.change_settings("System Settings", {"submission_queue_timeout": 3600})
	def test_submission_queue_uses_submission_queue_timeout(self):
		from frappe.core.doctype.submission_queue.submission_queue import queue_submission

		with self.set_user("test@example.com"):
			todo = frappe.get_doc({"doctype": "ToDo", "description": "Submission Queue Timeout"}).insert()
			self.addCleanup(todo.unlock)
			with patch("frappe.utils.background_jobs.enqueue") as enqueue:
				queue_submission(todo, "submit", alert=False)

		self.assertEqual(enqueue.call_args.kwargs["timeout"], 3600)
