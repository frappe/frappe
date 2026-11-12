# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.api import bulk, bulk_actions
from frappe.tests import IntegrationTestCase
from frappe.utils.task_queue import _execute_task

PREFIX = "bulk47065"


class TestBulkPrint(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(self.cleanup)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.form_dict.clear()
		frappe.cache.delete(frappe.cache.make_key(f"rl:multi_pdf_async:{frappe.session.user}"))
		self.names = [self.make_todo(i) for i in range(3)]

	def cleanup(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for name in frappe.get_all("ToDo", {"description": ["like", f"{PREFIX}%"]}, pluck="name"):
			frappe.delete_doc("ToDo", name, force=True)
		frappe.db.delete("Background Task", {"task_name": ["like", "Print %"]})
		frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 0)
		frappe.db.set_single_value("Print Settings", "max_concurrent_bulk_exports", 0)
		frappe.cache.delete(frappe.cache.make_key(f"rl:multi_pdf_async:{frappe.session.user}"))
		frappe.db.commit()  # nosemgrep

	def make_todo(self, index: int) -> str:
		return frappe.get_doc({"doctype": "ToDo", "description": f"{PREFIX} {index}"}).insert().name

	def post(self, names=None, **body):
		"""Call the route and return its response and what the worker would be given."""
		frappe.form_dict.update({"names": self.names if names is None else names, **body})
		with patch("frappe.utils.task_queue.frappe.enqueue") as enqueue:
			response = bulk_actions.bulk_print_docs("ToDo")
			frappe.db.commit()  # nosemgrep

		options = ("queue", "timeout", "deduplicate", "job_id", "at_front", "now", "at_front_when_starved")
		kwargs = {k: v for k, v in enqueue.call_args.kwargs.items() if k not in (*options, "rq_retry")}
		return response, kwargs

	def run_task(self, names=None, **body):
		response, kwargs = self.post(names, **body)
		_execute_task(**kwargs)
		task = frappe.db.get_value("Background Task", response["task_id"], ["status", "result"], as_dict=True)
		return task.status, frappe.parse_json(task.result)

	def test_one_record_still_runs_in_the_background(self):
		response, _kwargs = self.post(self.names[:1])

		self.assertEqual(frappe.response.http_status_code, 202)
		self.assertEqual(response["task_id"], response["job_id"])
		self.assertEqual(frappe.db.get_value("Background Task", response["task_id"], "status"), "Queued")

	def test_the_result_carries_one_merged_pdf(self):
		status, result = self.run_task()

		self.assertEqual(status, "Completed")
		self.assertEqual((result["total"], len(result["done"]), result["failed"]), (3, 3, []))
		file = frappe.get_doc("File", {"file_url": result["file_url"].split("?")[0]})
		self.addCleanup(frappe.delete_doc, "File", file.name, force=True)
		self.assertTrue(file.is_private)

		from io import BytesIO

		from pypdf import PdfReader

		self.assertGreaterEqual(len(PdfReader(BytesIO(file.get_content())).pages), 3)

	def test_a_missing_record_fails_alone(self):
		status, result = self.run_task([*self.names[:2], f"{PREFIX} missing"])

		self.assertEqual(status, "Completed")
		self.assertEqual(result["done"], self.names[:2])
		self.assertEqual([f["name"] for f in result["failed"]], [f"{PREFIX} missing"])
		self.assertIn("file_url", result)

	def test_no_file_when_every_record_fails(self):
		_status, result = self.run_task([f"{PREFIX} missing"])

		self.assertEqual(result["done"], [])
		self.assertNotIn("file_url", result)

	def test_page_size_reaches_the_pdf_options(self):
		with patch("frappe.api.bulk_actions.append_to_pdf") as append:
			self.run_task(self.names[:1], page_size="A5", print_format="Standard", no_letterhead="1")

		args = append.call_args.args
		self.assertEqual(args[3:7], ("Standard", True, None, {"page-size": "A5"}))

	def test_print_settings_cap_refuses_before_anything_runs(self):
		frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 2)

		with self.assertRaises(frappe.ValidationError):
			self.post()
		self.assertFalse(frappe.db.exists("Background Task", {"task_name": "Print ToDo"}))

	def test_print_cap_does_not_move_the_site_cap(self):
		frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 2)

		self.assertEqual(bulk.get_limit(), 500)

	def test_filters_stop_at_the_print_cap(self):
		frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 2)
		frappe.form_dict.update({"filters": {"description": ["like", f"{PREFIX}%"]}})

		with self.assertRaises(frappe.ValidationError):
			bulk_actions.bulk_print_docs("ToDo")

	def test_gate_off_refuses(self):
		frappe.db.set_value("User", "Administrator", "bulk_actions", 0)
		frappe.clear_document_cache("User", "Administrator")
		self.addCleanup(frappe.db.set_value, "User", "Administrator", "bulk_actions", 1)
		self.addCleanup(frappe.clear_document_cache, "User", "Administrator")

		with self.assertRaises(frappe.PermissionError):
			self.post()

	def test_user_without_print_permission_fails_each_record(self):
		with patch("frappe.api.bulk_actions.append_to_pdf", side_effect=frappe.PermissionError("no print")):
			status, result = self.run_task()

		self.assertEqual(status, "Completed")
		self.assertEqual(len(result["failed"]), 3)
		self.assertNotIn("file_url", result)

	def test_requests_are_paced(self):
		frappe.db.set_single_value("Print Settings", "max_concurrent_bulk_exports", 20)
		with patch("frappe.utils.task_queue.frappe.enqueue"):
			for _ in range(10):
				frappe.form_dict.update({"names": self.names[:1]})
				bulk_actions.bulk_print_docs("ToDo")

			with self.assertRaises(frappe.RateLimitExceededError):
				bulk_actions.bulk_print_docs("ToDo")

	def test_exports_in_progress_are_capped_per_user(self):
		frappe.db.set_single_value("Print Settings", "max_concurrent_bulk_exports", 1)
		self.post(self.names[:1])

		with self.assertRaises(frappe.RateLimitExceededError):
			self.post(self.names[:1])

	def test_boot_sends_the_print_cap(self):
		from frappe.shell.boot import core_boot

		frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 7)

		self.assertEqual(core_boot()["max_bulk_print_docs"], 7)
