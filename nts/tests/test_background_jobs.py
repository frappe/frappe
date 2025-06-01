import time
from contextlib import contextmanager
from unittest.mock import patch

from rq import Queue

import nts
from nts.core.doctype.rq_job.rq_job import remove_failed_jobs
from nts.tests.utils import ntsTestCase
from nts.utils.background_jobs import (
	RQ_JOB_FAILURE_TTL,
	RQ_RESULTS_TTL,
	create_job_id,
	execute_job,
	generate_qname,
	get_redis_conn,
)


class TestBackgroundJobs(ntsTestCase):
	def test_remove_failed_jobs(self):
		nts.enqueue(method="nts.tests.test_background_jobs.fail_function", queue="short")
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
			"method": "nts.handler.ping",
			"queue": "short",
		}

		# give worker something to work on first so that get_position doesn't return None
		nts.enqueue(**kwargs)

		# test enqueue with at_front=True
		low_priority_job = nts.enqueue(**kwargs)
		high_priority_job = nts.enqueue(**kwargs, at_front=True)

		# lesser is earlier
		self.assertTrue(high_priority_job.get_position() < low_priority_job.get_position())

	def test_job_hooks(self):
		self.addCleanup(lambda: _test_JOB_HOOK.clear())
		with freeze_local() as locals, nts.init_site(locals.site), patch(
			"nts.get_hooks", patch_job_hooks
		):
			nts.connect()
			self.assertIsNone(_test_JOB_HOOK.get("before_job"))
			r = execute_job(
				site=nts.local.site,
				user="Administrator",
				method="nts.handler.ping",
				event=None,
				job_name="nts.handler.ping",
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
	locals = nts.local
	nts.local = nts.Local()
	yield locals
	nts.local = locals


def patch_job_hooks(event: str):
	return {
		"before_job": ["nts.tests.test_background_jobs.before_job"],
		"after_job": ["nts.tests.test_background_jobs.after_job"],
	}[event]
