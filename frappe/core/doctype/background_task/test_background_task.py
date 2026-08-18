import time
from unittest.mock import patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.tests import IntegrationTestCase
from frappe.utils.task_queue import _execute_task, enqueue_task, get_current_task, get_task_status


def sample_task(value=1):
	return {"value": value}


def sample_task_with_updates(total=3):
	handle = get_current_task()
	for i in range(1, total + 1):
		handle.update_stage(f"Step {i}")
		handle.publish_progress((i / total) * 100)
		if i < total:
			time.sleep(0.3)


def sample_task_intermediate_result():
	handle = get_current_task()
	handle.store_result({"partial": True})


def sample_task_with_attachment():
	handle = get_current_task()
	handle.attach_file(file_name="bg-task-output.txt", content=b"done")
	return {"success": True}


def failing_task():
	raise ValueError("Intentional test failure")


def _always_raise(*args, **kwargs):
	raise RuntimeError("callback error")


class IntegrationTestBackgroundTask(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		# prevent enqueue_task from creating real RQ jobs in Redis.
		self.enqueue_patcher = patch("frappe.utils.task_queue.frappe.enqueue")
		self.mock_enqueue = self.enqueue_patcher.start()

	def tearDown(self):
		self.enqueue_patcher.stop()
		super().tearDown()

	def test_enqueue_and_success_lifecycle(self):
		doc = enqueue_task(sample_task, task_name="Test success", value=42)
		self.assertEqual(get_task_status(doc.task_id)["status"], "Queued")

		_execute_task(doc.task_id, sample_task, frappe.session.user, value=42)

		doc.reload()
		self.assertEqual(doc.status, "Completed")
		self.assertIn("42", doc.result)

	def test_failed_task_stores_exception(self):
		doc = enqueue_task(failing_task, task_name="Test failure")
		with self.assertRaises(ValueError):
			_execute_task(doc.task_id, failing_task, frappe.session.user)

		doc.reload()
		self.assertEqual(doc.status, "Failed")
		self.assertIn("Intentional test failure", doc.exception)

	def test_attach_file_links_file_to_task(self):
		doc = enqueue_task(sample_task_with_attachment, task_name="Test attachment")
		_execute_task(doc.task_id, sample_task_with_attachment, frappe.session.user)

		attached_files = frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Background Task", "attached_to_name": doc.name},
			pluck="name",
		)
		self.assertTrue(len(attached_files) > 0)

	def test_attach_file_prefers_ref_document(self):
		test_doctype = new_doctype().insert()
		test_doc = frappe.get_doc({"doctype": test_doctype.name}).insert()

		task = enqueue_task(
			sample_task_with_attachment,
			task_name="Test attachment with ref",
			ref_doctype=test_doctype.name,
			ref_docname=test_doc.name,
		)
		_execute_task(task.task_id, sample_task_with_attachment, frappe.session.user)

		attached_files = frappe.get_all(
			"File",
			filters={"attached_to_doctype": test_doctype.name, "attached_to_name": test_doc.name},
			pluck="name",
		)
		self.assertTrue(len(attached_files) > 0)

	def test_on_success_callback_is_called(self):
		doc = enqueue_task(sample_task, on_success=sample_task, value=42)

		with patch("frappe.utils.task_queue._run_callback") as mock_callback:
			_execute_task(
				doc.task_id,
				sample_task,
				frappe.session.user,
				task_on_success=doc.on_success_callback,
				value=42,
			)

		mock_callback.assert_called_once()
		_, call_kwargs = mock_callback.call_args
		self.assertEqual(call_kwargs["result"], {"value": 42})

	def test_on_failure_callback_is_called(self):
		doc = enqueue_task(failing_task, on_failure=sample_task)

		with patch("frappe.utils.task_queue._run_callback") as mock_callback:
			with self.assertRaises(ValueError):
				_execute_task(
					doc.task_id, failing_task, frappe.session.user, task_on_failure=doc.on_failure_callback
				)

		mock_callback.assert_called_once()
		_, call_kwargs = mock_callback.call_args
		self.assertIsInstance(call_kwargs["exception"], ValueError)

	def test_callback_failure_does_not_change_task_status(self):
		doc = enqueue_task(sample_task, on_success=_always_raise, value=1)
		_execute_task(
			doc.task_id, sample_task, frappe.session.user, task_on_success=doc.on_success_callback, value=1
		)
		doc.reload()
		self.assertEqual(doc.status, "Completed")

	def test_callback_receives_only_declared_params(self):
		from frappe.utils.task_queue import _run_callback

		received = {}

		def capture_result(result):
			received["result"] = result

		task_doc = enqueue_task(sample_task, value=5)
		_run_callback(capture_result, task_doc, task_kwargs={"value": 5}, result={"value": 5})

		self.assertEqual(received["result"], {"value": 5})
		self.assertNotIn("task", received)
		self.assertNotIn("value", received)

	def test_callback_var_keyword_receives_full_context(self):
		from frappe.utils.task_queue import _run_callback

		received = {}

		def capture_all(**kwargs):
			received.update(kwargs)

		task_doc = enqueue_task(sample_task, value=5)
		_run_callback(capture_all, task_doc, task_kwargs={"value": 5}, result={"value": 5})

		self.assertIn("task", received)
		self.assertIn("result", received)
		self.assertIn("value", received)

	def test_callbacks_stored_as_dotted_paths(self):
		doc = enqueue_task(sample_task, on_success=sample_task, on_failure=failing_task)
		self.assertIn("sample_task", doc.on_success_callback)
		self.assertIn("failing_task", doc.on_failure_callback)

	def test_retry_passes_stored_callbacks(self):
		from frappe.core.doctype.background_task.background_task import retry_task

		doc = enqueue_task(failing_task, on_success=sample_task, on_failure=sample_task)
		doc.db_set("status", "Failed")

		retry_task(doc.task_id)

		call_kwargs = self.mock_enqueue.call_args.kwargs
		self.assertEqual(call_kwargs["task_on_success"], doc.on_success_callback)
		self.assertEqual(call_kwargs["task_on_failure"], doc.on_failure_callback)

	def test_retriable_exception_keeps_status_running(self):
		doc = enqueue_task(failing_task, retry_on=(ValueError,), max_retries=3)

		fake_job = type("FakeJob", (), {"retries_left": 3})()
		with patch("frappe.utils.task_queue._current_rq_job", return_value=fake_job):
			with self.assertRaises(ValueError):
				_execute_task(doc.task_id, failing_task, frappe.session.user, task_retry_on=(ValueError,))

		doc.reload()
		self.assertEqual(doc.status, "Running")
		self.assertIsNone(doc.exception)
		self.assertEqual(fake_job.retries_left, 3)

	def test_non_retriable_exception_marks_failed_and_zeros_retries(self):
		doc = enqueue_task(failing_task, retry_on=(KeyError,), max_retries=3)

		fake_job = type("FakeJob", (), {"retries_left": 3})()
		with patch("frappe.utils.task_queue._current_rq_job", return_value=fake_job):
			with self.assertRaises(ValueError):
				_execute_task(doc.task_id, failing_task, frappe.session.user, task_retry_on=(KeyError,))

		doc.reload()
		self.assertEqual(doc.status, "Failed")
		self.assertEqual(fake_job.retries_left, 0)

	def test_retries_exhausted_marks_failed(self):
		doc = enqueue_task(failing_task, retry_on=(ValueError,), max_retries=3)

		fake_job = type("FakeJob", (), {"retries_left": 0})()
		with patch("frappe.utils.task_queue._current_rq_job", return_value=fake_job):
			with self.assertRaises(ValueError):
				_execute_task(doc.task_id, failing_task, frappe.session.user, task_retry_on=(ValueError,))

		doc.reload()
		self.assertEqual(doc.status, "Failed")

	@patch("rq.job.Job.fetch")
	def test_stop_task_cancels_queued_task(self, mock_job_fetch):
		from frappe.core.doctype.background_task.background_task import stop_task

		doc = enqueue_task(sample_task, task_name="Test stop", enqueue_after_commit=False)

		# Cancel the queued task
		stop_task(doc.task_id)

		doc.reload()
		self.assertEqual(doc.status, "Cancelled")

		# If execute is called (worker picking it up later), it should abort early
		_execute_task(doc.task_id, sample_task, frappe.session.user)

		doc.reload()
		self.assertEqual(doc.status, "Cancelled")
		self.assertIsNone(doc.result)
