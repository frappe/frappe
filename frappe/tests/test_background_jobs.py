import time
from contextlib import contextmanager
from contextvars import copy_context
from unittest.mock import patch

from rq import Queue
from werkzeug.local import Local

import frappe
from frappe.core.doctype.rq_job.rq_job import remove_failed_jobs
from frappe.tests import IntegrationTestCase
from frappe.tests.utils.test_capabilities import TestService, requires_test_service
from frappe.utils.background_jobs import (
	RQ_JOB_FAILURE_TTL,
	RQ_RESULTS_TTL,
	create_job_id,
	execute_job,
	generate_qname,
	get_queues_timeout,
	get_redis_conn,
)


class TestBackgroundJobs(IntegrationTestCase):
	@requires_test_service(TestService.BACKGROUND_WORKER)
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

	def test_get_queues_timeout_tolerates_invalid_workers_config(self):
		builtin = {"short", "default", "long"}
		self.addCleanup(get_queues_timeout.cache_clear)

		with patch("frappe.get_conf", return_value={"workers": 8}):
			get_queues_timeout.cache_clear()
			timeouts = get_queues_timeout()
		self.assertEqual(set(timeouts), builtin)

		with patch("frappe.get_conf", return_value={"workers": {"long": 999, "custom": {"timeout": 5000}}}):
			get_queues_timeout.cache_clear()
			timeouts = get_queues_timeout()
		self.assertEqual(timeouts["custom"], 5000)
		self.assertEqual(timeouts["long"], 1500)
		self.assertLessEqual(builtin, set(timeouts))

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

	def test_job_translation_resolves_user_language(self):
		real_get_cached_value = frappe.get_cached_value

		def user_language_de(doctype, name, fieldname=None, *args, **kwargs):
			if doctype == "User" and fieldname == "language":
				return "de"
			return real_get_cached_value(doctype, name, fieldname, *args, **kwargs)

		frappe.local.job = frappe._dict(user="Administrator")
		self.addCleanup(delattr, frappe.local, "job")
		original_lang = frappe.local.lang
		self.addCleanup(setattr, frappe.local, "lang", original_lang)
		frappe.local.lang = "en"

		with patch("frappe.get_cached_value", side_effect=user_language_de):
			frappe._("Home")

		self.assertEqual(frappe.local.lang, "de")

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

	def test_job_retries_framework_deadlock_errors(self):
		attempts = 0

		def locked_once():
			nonlocal attempts
			attempts += 1
			if attempts == 1:
				raise frappe.QueryDeadlockError("database is locked")
			return "completed"

		with (
			patch.object(frappe.db, "rollback") as rollback,
			patch.object(frappe.db, "commit") as commit,
			patch("frappe.utils.background_jobs.time.sleep") as sleep,
			patch("frappe.utils.background_jobs.frappe.destroy"),
			patch("frappe.utils.background_jobs.frappe.get_hooks", return_value=[]),
		):
			result = execute_job(
				site=frappe.local.site,
				method=locked_once,
				event=None,
				job_name="locked-once",
				kwargs={},
				is_async=False,
			)

		self.assertEqual(result, "completed")
		self.assertEqual(attempts, 2)
		rollback.assert_called_once_with(chain=True)
		commit.assert_called_once_with(chain=True)
		sleep.assert_called_once_with(1)

	def test_async_job_retry_keeps_cleanup_context(self):
		attempts = 0
		after_job_calls = 0
		database_class = type(frappe.local.db)
		site = frappe.local.site

		def record_after_job():
			nonlocal after_job_calls
			after_job_calls += 1

		def locked_once():
			nonlocal attempts
			attempts += 1
			if attempts == 1:
				raise frappe.QueryDeadlockError("database is locked")
			frappe.local.job.after_job.add(record_after_job)
			return "completed"

		with (
			patch.object(database_class, "rollback"),
			patch.object(database_class, "commit"),
			patch("frappe.utils.background_jobs.time.sleep"),
			patch("frappe.utils.background_jobs.frappe.get_hooks", return_value=[]),
		):
			result = copy_context().run(
				execute_job,
				site,
				locked_once,
				None,
				"async-locked-once",
				{},
				is_async=True,
			)

		self.assertEqual(result, "completed")
		self.assertEqual(attempts, 2)
		self.assertEqual(after_job_calls, 1)

	def test_job_retry_preserves_user(self):
		def locked_once():
			raise frappe.QueryDeadlockError("database is locked")

		with (
			patch("frappe.utils.background_jobs.execute_job", return_value="completed") as retry_job,
			patch("frappe.utils.background_jobs.time.sleep"),
			patch("frappe.utils.background_jobs.frappe.destroy"),
			patch("frappe.utils.background_jobs.frappe.get_hooks", return_value=[]),
		):
			result = execute_job(
				site=frappe.local.site,
				user="test@example.com",
				method=locked_once,
				event=None,
				job_name="locked-once-as-user",
				is_async=False,
				kwargs={},
			)

		self.assertEqual(result, "completed")
		retry_job.assert_called_once_with(
			frappe.local.site,
			locked_once,
			None,
			"locked-once-as-user",
			{},
			user="test@example.com",
			is_async=False,
			retry=1,
		)


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
	try:
		yield locals
	finally:
		# without the restore, every test running after this one in the same
		# process sees an unbound frappe.local and fails
		frappe.local = locals


_real_get_hooks = frappe.get_hooks


def patch_job_hooks(event: str, *args, **kwargs):
	test_hooks = {
		"before_job": ["frappe.tests.test_background_jobs.before_job"],
		"after_job": ["frappe.tests.test_background_jobs.after_job"],
	}
	if event in test_hooks:
		return test_hooks[event]
	# anything else the job execution looks up (e.g. typing_validations'
	# require_type_annotated_api_methods) must behave as usual
	return _real_get_hooks(event, *args, **kwargs)
