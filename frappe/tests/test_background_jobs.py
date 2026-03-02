import time
from contextlib import contextmanager
from unittest.mock import patch

from rq import Queue
from werkzeug.local import Local

import frappe
from frappe.core.doctype.rq_job.rq_job import remove_failed_jobs
from frappe.tests import IntegrationTestCase
from frappe.utils.background_jobs import (
	RQ_JOB_FAILURE_TTL,
	RQ_RESULTS_TTL,
	create_job_id,
	execute_job,
	generate_qname,
	get_redis_conn,
)


class TestBackgroundJobs(IntegrationTestCase):
	def test_remove_failed_jobs(self):
		frappe.enqueue(method="frappe.tests.test_background_jobs.fail_function", queue="short")
		# wait for enqueued job to execute
		time.sleep(2)
		conn = get_redis_conn()
		queues = Queue.all(conn)

		for queue in queues:
			if queue.name == generate_qname("short"):
				fail_registry = queue.failed_job_registry
				self.assertGreater(fail_registry.count, 0)

		remove_failed_jobs()

		for queue in queues:
			if queue.name == generate_qname("short"):
				fail_registry = queue.failed_job_registry
				self.assertEqual(fail_registry.count, 0)

	def test_enqueue_at_front(self):
		kwargs = {
			"method": "frappe.handler.ping",
			"queue": "short",
		}

		# give worker something to work on first so that get_position doesn't return None
		frappe.enqueue(**kwargs)

		# test enqueue with at_front=True
		low_priority_job = frappe.enqueue(**kwargs)
		high_priority_job = frappe.enqueue(**kwargs, at_front=True)

		# lesser is earlier
		self.assertTrue(high_priority_job.get_position() < low_priority_job.get_position())

	def test_query_deadlock_error_retries_job(self):
		"""QueryDeadlockError raised by frappe.db.sql should trigger job retry."""
		call_count = 0

		def deadlock_once(**kwargs):
			nonlocal call_count
			call_count += 1
			if call_count == 1:
				raise frappe.QueryDeadlockError(1020, "Record has changed since last read in table 'tabContact'")
			return "success"

		with (
			freeze_local() as locals,
			frappe.init_site(locals.site),
			patch("time.sleep"),
		):
			frappe.connect()
			result = execute_job(
				site=frappe.local.site,
				user="Administrator",
				method=deadlock_once,
				event=None,
				job_name="test_deadlock",
				is_async=True,
				kwargs={},
			)
			self.assertEqual(result, "success")
			self.assertEqual(call_count, 2)

	def test_query_timeout_error_retries_job(self):
		"""QueryTimeoutError raised by frappe.db.sql should trigger job retry."""
		call_count = 0

		def timeout_once(**kwargs):
			nonlocal call_count
			call_count += 1
			if call_count == 1:
				raise frappe.QueryTimeoutError(1205, "Lock wait timeout exceeded")
			return "success"

		with (
			freeze_local() as locals,
			frappe.init_site(locals.site),
			patch("time.sleep"),
		):
			frappe.connect()
			result = execute_job(
				site=frappe.local.site,
				user="Administrator",
				method=timeout_once,
				event=None,
				job_name="test_timeout",
				is_async=True,
				kwargs={},
			)
			self.assertEqual(result, "success")
			self.assertEqual(call_count, 2)

	def test_job_hooks(self):
		self.addCleanup(lambda: _test_JOB_HOOK.clear())
		with (
			freeze_local() as locals,
			frappe.init_site(locals.site),
			patch("frappe.get_hooks", patch_job_hooks),
		):
			frappe.connect()
			self.assertIsNone(_test_JOB_HOOK.get("before_job"))
			r = execute_job(
				site=frappe.local.site,
				user="Administrator",
				method="frappe.handler.ping",
				event=None,
				job_name="frappe.handler.ping",
				is_async=True,
				kwargs={},
			)
			self.assertEqual(r, "pong")
			self.assertLess(_test_JOB_HOOK.get("before_job"), _test_JOB_HOOK.get("after_job"))


def fail_function():
	return 1 / 0


_test_JOB_HOOK = {}


def before_job(*args, **kwargs):
	_test_JOB_HOOK["before_job"] = time.time()


def after_job(*args, **kwargs):
	_test_JOB_HOOK["after_job"] = time.time()


@contextmanager
def freeze_local():
	locals = frappe.local
	frappe.local = Local()
	yield locals
	frappe.local = locals


def patch_job_hooks(event: str):
	return {
		"before_job": ["frappe.tests.test_background_jobs.before_job"],
		"after_job": ["frappe.tests.test_background_jobs.after_job"],
	}[event]
