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
	get_queues_timeout,
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
