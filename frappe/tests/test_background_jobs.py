import time
import unittest

from rq import Queue

import frappe
from frappe.core.page.background_jobs.background_jobs import remove_failed_jobs
from frappe.utils.background_jobs import get_redis_conn


class TestBackgroundJobs(unittest.TestCase):
	def test_remove_failed_jobs(self):
		frappe.enqueue(method="frappe.tests.test_background_jobs.fail_function", queue="short")
		# wait for enqueued job to execute
		time.sleep(2)
		conn = get_redis_conn()
		queues = Queue.all(conn)

		for queue in queues:
			if queue.name == "short":
				fail_registry = queue.failed_job_registry
				self.assertGreater(fail_registry.count, 0)

		remove_failed_jobs()

		for queue in queues:
			if queue.name == "short":
				fail_registry = queue.failed_job_registry
				self.assertEqual(fail_registry.count, 0)


def fail_function():
	return 1 / 0
