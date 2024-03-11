import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

from rq import Queue

import frappe
from frappe.core.doctype.rq_job.rq_job import remove_failed_jobs
from frappe.tests.utils import FrappeTestCase
from frappe.utils.background_jobs import (
	RQ_JOB_FAILURE_TTL,
	RQ_RESULTS_TTL,
	create_job_id,
	execute_job,
	generate_qname,
	get_redis_conn,
)


class TestBackgroundJobs(FrappeTestCase):
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

	def test_job_hooks(self):
		self.addCleanup(lambda: _test_JOB_HOOK.clear())
		with freeze_local() as locals, frappe.init_site(locals.site), patch(
			"frappe.get_hooks", patch_job_hooks
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

	def test_enqueue_with_without_scheduledjob(self):
		kwargs = {
			"method": "frappe.handler.ping",
			"queue": "short",
		}

		# give worker something to work on first so that get_position doesn't return None
		frappe.enqueue(**kwargs)

		# test enqueue with and without datetime
		instant_job = frappe.enqueue(**kwargs)
		scheduled_job = frappe.enqueue(**kwargs, schedule_at=datetime.now() + timedelta(minutes=5))

		# checking if the job is scheduled or not
		self.assertTrue(instant_job.get_position() >= 0)
		# Checking if the status of the job is scheduled or not
		self.assertTrue(instant_job.get_status().casefold() != "SCHEDULED".casefold())

		#  For scheduled job to be executed
		self.assertTrue(scheduled_job.get_position() is None)
		# Checking if the status of the job is scheduled or not
		self.assertTrue(scheduled_job.get_status().casefold() == "SCHEDULED".casefold())

	def test_enqueue_with_old_datetime_scheduling(self):
		kwargs = {
			"method": "frappe.handler.ping",
			"queue": "short",
		}

		# give worker something to work on first so that get_position doesn't return None
		frappe.enqueue(**kwargs)

		# test enqueue with old datetime
		schedule_job = frappe.enqueue(**kwargs, schedule_at=datetime.now() - timedelta(hours=10))
		self.assertTrue(schedule_job.get_status().casefold() != "SCHEDULED".casefold())

	def test_enqueue_with_no_schedule_at_input(self):
		kwargs = {
			"method": "frappe.handler.ping",
			"queue": "short",
		}

		# give worker something to work on first so that get_position doesn't return None
		frappe.enqueue(**kwargs)

		# test enqueue with no datetime, this should work like enqueue
		schedule_job = frappe.enqueue(**kwargs)
		self.assertTrue(schedule_job.get_status().casefold() != "SCHEDULED".casefold())

	def test_enqueue_with_scheduled_job_until_executed(self):
		kwargs = {
			"method": "frappe.handler.ping",
			"queue": "short",
		}

		# give worker something to work on first so that get_position doesn't return None
		frappe.enqueue(**kwargs)

		# schedule a job to be executed after 15 seconds
		scheduled_job = frappe.enqueue(**kwargs, schedule_at=datetime.now() + timedelta(seconds=15))
		job_start_time = datetime.now()
		job_end_time = datetime.now()

		#  Assetting the status of the job is scheduled and not queued
		self.assertTrue(scheduled_job.get_position() is None)
		self.assertTrue(scheduled_job.get_status().casefold() == "SCHEDULED".casefold())

		for _ in range(0, 100000):
			time.sleep(0.05)
			if scheduled_job.get_status().casefold() == "finished".casefold():
				job_end_time = datetime.now()
				break

		# Checking if the status of the job is finished or not
		self.assertEqual(scheduled_job.get_status().casefold(), "finished".casefold())

		# Checking if the job is executed after 15 seconds
		time_taken_in_seconds = (job_end_time - job_start_time).seconds
		self.assertTrue(time_taken_in_seconds >= 14)


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
	frappe.local = frappe.Local()
	yield locals
	frappe.local = locals


def patch_job_hooks(event: str):
	return {
		"before_job": ["frappe.tests.test_background_jobs.before_job"],
		"after_job": ["frappe.tests.test_background_jobs.after_job"],
	}[event]
