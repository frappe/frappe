"""Tests for the lifecycle of `frappe.local` across requests and background jobs.

Web worker threads (gunicorn gthread) and in-process RQ workers reuse one context for many
requests or jobs. If the cleanup at the end of one request/job fails, the next one must still
start with a clean `frappe.local`: no stale attributes, flags, user or DB connection.

Most scenarios run in a dedicated thread. A new thread starts with an empty context, so the
scenario behaves like one long-lived worker thread and never touches this test's `frappe.local`.
"""

import contextvars
import gc
import inspect
import sys
import threading
import time
import unittest
from unittest.mock import patch

from rq import Queue, SimpleWorker
from werkzeug.test import Client

import frappe
import frappe.app
from frappe.tests import IntegrationTestCase
from frappe.utils import cint
from frappe.utils.background_jobs import execute_job, get_redis_conn

POISON = "left-behind-by-previous-request-or-job"
TEST_USER = "local-lifecycle@example.com"

# Probe endpoints. They are whitelisted only while these tests run, see `_whitelist_endpoints`.
ENDPOINTS = ("probe", "poison_only", "poison_and_break_cleanup", "request_info")

# What a request/job must see if nothing leaked from a previous one.
CLEAN = {
	"stale_marker": None,
	"flags_poisoned": False,
	"has_primary_db": False,
	"has_replica_db": False,
	"poison_in_message_log": False,
	"form_dict_poisoned": None,
	"cache_poisoned": None,
	"request_cache_poisoned": False,
}

_states = []
_after_response_sites = []


class CleanupFailed(Exception):
	pass


def _break_cleanup():
	raise CleanupFailed


class _Thread:
	"""Run a function in a new thread (with a fresh, empty context) and collect its outcome."""

	def __init__(self, fn, *args, **kwargs):
		self._outcome = {}
		self._thread = threading.Thread(target=self._run, args=(fn, args, kwargs))
		self._thread.start()

	def _run(self, fn, args, kwargs):
		try:
			self._outcome["result"] = fn(*args, **kwargs)
		except BaseException as e:
			self._outcome["error"] = e

	def result(self, timeout=300):
		self._thread.join(timeout)
		if self._thread.is_alive():
			raise TimeoutError("thread did not finish")
		if "error" in self._outcome:
			raise self._outcome["error"]
		return self._outcome.get("result")


def run_in_thread(fn, *args, **kwargs):
	return _Thread(fn, *args, **kwargs).result()


def connection_is_alive(connection_id, timeout=5.0) -> bool:
	"""Check if a DB connection is open. Waits up to `timeout` for the server to see it close."""
	gc.collect()
	deadline = time.monotonic() + timeout
	while True:
		alive = frappe.db.sql(
			"select count(*) from information_schema.processlist where id = %s", connection_id
		)[0][0]
		if not alive or time.monotonic() >= deadline:
			return bool(alive)
		time.sleep(0.1)


def poison_local():
	"""Leave state behind, the way a request/job does when its cleanup fails."""
	frappe.local.stale_marker = POISON
	frappe.local.flags.poisoned = True
	# `connect_replica` does not connect again if these exist
	frappe.local.primary_db = frappe.local.replica_db = POISON
	frappe.local.message_log.append({"message": POISON})
	frappe.local.form_dict.poisoned = POISON
	frappe.local.cache["poisoned"] = POISON
	frappe.local.request_cache["poisoned"]["value"] = POISON


def snapshot(stale_connection_id=None) -> dict:
	"""Describe what the current request/job sees in `frappe.local`."""
	job = getattr(frappe.local, "job", None) or {}
	return {
		"site": frappe.local.site,
		"user": frappe.session.user,
		"stale_marker": getattr(frappe.local, "stale_marker", None),
		"flags_poisoned": bool(frappe.local.flags.get("poisoned")),
		"has_primary_db": hasattr(frappe.local, "primary_db"),
		"has_replica_db": hasattr(frappe.local, "replica_db"),
		"poison_in_message_log": POISON in str(frappe.local.message_log),
		"form_dict_poisoned": frappe.local.form_dict.get("poisoned"),
		"cache_poisoned": frappe.local.cache.get("poisoned"),
		"request_cache_poisoned": bool(frappe.local.request_cache.get("poisoned")),
		"job_method": job.get("method"),
		"app_modules": sorted(frappe.local.app_modules or {}),
		"connection_id": frappe.db.sql("select connection_id()")[0][0],
		"stale_connection_alive": connection_is_alive(stale_connection_id) if stale_connection_id else None,
	}


# Request endpoints


def probe(stale_connection_id=None):
	return snapshot(cint(stale_connection_id) or None)


def poison_only():
	state = snapshot()
	poison_local()
	return state


def poison_and_break_cleanup():
	"""Leave state behind, then make the end-of-request cleanup fail before `frappe.destroy`."""
	state = snapshot()
	_states.append(state)
	poison_local()
	frappe.request.after_response.add(_break_cleanup)
	return state


def request_info():
	frappe.request.after_response.add(lambda: _after_response_sites.append(frappe.local.site))
	return {"is_ajax": frappe.local.is_ajax, "path": frappe.request.path}


# Job methods


def job_probe(stale_connection_id=None):
	return snapshot(stale_connection_id)


def job_probe_previous():
	"""Probe, and check that the connection of the previously recorded job is closed."""
	return snapshot(_states[-1]["connection_id"])


def job_poison_and_break_cleanup():
	"""Leave state behind, then make the end-of-job cleanup fail before `frappe.destroy`."""
	_states.append(snapshot())
	poison_local()
	frappe.job.after_job.add(_break_cleanup)


def job_retry_once():
	_states.append(snapshot())
	if len(_states) == 1:
		poison_local()
		raise frappe.RetryBackgroundJobError
	return _states[-1]


class TestLocalLifecycle(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = frappe.local.site
		cls._whitelist_endpoints()
		cls._create_api_user()

	@classmethod
	def _whitelist_endpoints(cls):
		"""Whitelist the probe endpoints only while these tests run.

		A module-level `@frappe.whitelist(allow_guest=True)` would expose them on every site."""
		module = sys.modules[__name__]
		for name in ENDPOINTS:
			original = getattr(module, name)
			wrapped = frappe.whitelist(allow_guest=True)(original)
			setattr(module, name, wrapped)
			cls.addClassCleanup(cls._unwhitelist, module, name, original, wrapped)

	@staticmethod
	def _unwhitelist(module, name, original, wrapped):
		setattr(module, name, original)
		frappe.whitelisted.discard(wrapped)
		frappe.guest_methods.discard(wrapped)
		frappe.allowed_http_methods_for_whitelisted_func.pop(wrapped, None)

	@classmethod
	def _create_api_user(cls):
		frappe.delete_doc_if_exists("User", TEST_USER, force=True)
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": TEST_USER,
				"first_name": "Local Lifecycle",
				"send_welcome_email": 0,
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_permissions=True)
		api_secret = frappe.generate_hash(length=15)
		user.api_key = frappe.generate_hash(length=15)
		user.api_secret = api_secret
		user.save(ignore_permissions=True)
		# requests and jobs use their own DB connection
		frappe.db.commit()
		cls.api_auth = f"token {user.api_key}:{api_secret}"
		cls.addClassCleanup(cls._delete_api_user)

	@staticmethod
	def _delete_api_user():
		frappe.delete_doc_if_exists("User", TEST_USER, force=True)
		frappe.db.commit()

	def setUp(self):
		_states.clear()
		_after_response_sites.clear()

	def assertClean(self, state):
		self.assertEqual({key: state[key] for key in CLEAN}, CLEAN)
		self.assertEqual(state["site"], self.site)

	def call(self, client, path, auth=None, headers=None, **params):
		"""GET `path` on this site. `path` without a slash is an endpoint in this module."""
		if "/" not in path:
			path = f"/api/method/{__name__}.{path}"
		headers = {"X-Frappe-Site-Name": self.site, **(headers or {})}
		if auth:
			headers["Authorization"] = auth
		return client.get(path, query_string=params, headers=headers, buffered=True)

	def run_job(self, method, user=None, is_async=True, **kwargs):
		return execute_job(
			site=self.site,
			method=f"{__name__}.{method}",
			event=None,
			job_name=method,
			kwargs=kwargs,
			user=user,
			is_async=is_async,
		)

	# frappe.init

	def test_force_init_discards_state_left_by_previous_context(self):
		def worker_thread():
			frappe.init(self.site)
			frappe.connect()
			poison_local()
			frappe.local.request = object()
			frappe.local.job = frappe._dict(method="stale.job")

			frappe.init(self.site, force=True)
			try:
				return {
					"initialised": frappe.local.initialised,
					"site": frappe.local.site,
					"leftover": [
						name
						for name in ("stale_marker", "primary_db", "replica_db", "request", "job", "db")
						if hasattr(frappe.local, name)
					],
					"flags_poisoned": bool(frappe.flags.get("poisoned")),
					"message_log": list(frappe.local.message_log),
					"form_dict": dict(frappe.local.form_dict),
					# `init` itself fills `local.cache` (e.g. module map), only check the leftover
					"cache_poisoned": "poisoned" in frappe.local.cache,
					"request_cache": dict(frappe.local.request_cache),
				}
			finally:
				frappe.destroy()

		self.assertEqual(
			run_in_thread(worker_thread),
			{
				"initialised": True,
				"site": self.site,
				"leftover": [],
				"flags_poisoned": False,
				"message_log": [],
				"form_dict": {},
				"cache_poisoned": False,
				"request_cache": {},
			},
		)

	def test_init_without_force_keeps_current_context(self):
		def worker_thread():
			frappe.init(self.site)
			flags = frappe.local.flags
			frappe.local.stale_marker = POISON
			frappe.init(self.site)
			try:
				return frappe.local.stale_marker, frappe.local.flags is flags
			finally:
				frappe.destroy()

		self.assertEqual(run_in_thread(worker_thread), (POISON, True))

	def test_force_init_builds_new_containers(self):
		"""Nothing that holds a container from the old context can see or change the new one."""
		names = (
			"flags",
			"conf",
			"response",
			"response_headers",
			"message_log",
			"error_log",
			"debug_log",
			"form_dict",
			"session",
			"cache",
			"request_cache",
			"locked_documents",
			"role_permissions",
		)

		def worker_thread():
			frappe.init(self.site)
			before = {name: getattr(frappe.local, name) for name in names}
			frappe.init(self.site, force=True)
			try:
				return [name for name in names if getattr(frappe.local, name) is before[name]]
			finally:
				frappe.destroy()

		self.assertEqual(run_in_thread(worker_thread), [])

	def test_force_init_in_copied_context_does_not_touch_parent_context(self):
		def worker_thread():
			frappe.init(self.site)
			frappe.local.marker = "parent"

			def child():
				frappe.init(self.site, force=True)
				frappe.local.marker = "child"
				return frappe.local.marker

			child_marker = contextvars.copy_context().run(child)
			try:
				return child_marker, frappe.local.marker, frappe.local.site
			finally:
				frappe.destroy()

		self.assertEqual(run_in_thread(worker_thread), ("child", "parent", self.site))

	def test_force_init_does_not_affect_other_threads(self):
		"""Like the scheduler thread of a worker next to the job thread, or gthread web threads."""
		ready = threading.Barrier(2, timeout=60)
		churn_done = threading.Event()

		def long_lived_thread():
			frappe.init(self.site)
			frappe.connect()
			frappe.local.marker = "long-lived"
			connection_id = frappe.db.sql("select connection_id()")[0][0]
			ready.wait()
			churn_done.wait(120)
			try:
				return (
					frappe.local.marker,
					frappe.local.site,
					frappe.db.sql("select connection_id()")[0][0] == connection_id,
				)
			finally:
				frappe.destroy()

		def churn_thread():
			ready.wait()
			try:
				for _ in range(20):
					frappe.init(self.site, force=True, is_job=True)
					frappe.connect()
					frappe.local.marker = "churn"
					frappe.destroy()
			finally:
				churn_done.set()

		long_lived = _Thread(long_lived_thread)
		run_in_thread(churn_thread)
		self.assertEqual(long_lived.result(), ("long-lived", self.site, True))

	def test_request_and_job_flags_are_keyword_only(self):
		params = inspect.signature(frappe.init).parameters
		# positional arguments keep their old meaning
		self.assertEqual(list(params)[:4], ["site", "sites_path", "new_site", "force"])
		for name in ("is_request", "is_job"):
			self.assertEqual(params[name].kind, inspect.Parameter.KEYWORD_ONLY)
			self.assertIs(params[name].default, False)

	def _init_mode(self, prepare=None, **init_kwargs):
		"""Return `(cached site config, include_all_apps)` used by `frappe.init`."""

		def worker_thread():
			frappe.init(self.site)
			if prepare:
				prepare()
			with (
				patch("frappe.get_site_config", wraps=frappe.get_site_config) as get_site_config,
				patch("frappe.setup_module_map", wraps=frappe.setup_module_map) as setup_module_map,
			):
				frappe.init(self.site, force=True, **init_kwargs)
			try:
				return (
					get_site_config.call_args.kwargs["cached"],
					setup_module_map.call_args.kwargs["include_all_apps"],
				)
			finally:
				frappe.destroy()

		return run_in_thread(worker_thread)

	def test_site_config_caching_and_module_map_follow_init_mode(self):
		self.assertEqual(self._init_mode(), (False, True))
		self.assertEqual(self._init_mode(is_request=True), (True, False))
		self.assertEqual(self._init_mode(is_job=True), (False, False))

	def test_leftover_request_or_job_does_not_change_init_mode(self):
		"""`init` used to look at `frappe.request` / `frappe.job`, which could be left over."""

		def leave_request_and_job():
			frappe.local.request = object()
			frappe.local.job = frappe._dict(method="stale.job")

		self.assertEqual(self._init_mode(prepare=leave_request_and_job), (False, True))

	# frappe.destroy

	def test_destroy_releases_local_even_if_closing_db_fails(self):
		def worker_thread():
			frappe.init(self.site)
			frappe.connect()
			db = frappe.local.db
			try:
				with patch.object(db, "close", side_effect=CleanupFailed), self.assertRaises(CleanupFailed):
					frappe.destroy()
				return hasattr(frappe.local, "site"), hasattr(frappe.local, "db"), bool(frappe.db)
			finally:
				db.close()

		self.assertEqual(run_in_thread(worker_thread), (False, False, False))

	def test_destroy_closes_connection_and_releases_local(self):
		def worker_thread():
			frappe.init(self.site)
			frappe.connect()
			connection_id = frappe.db.sql("select connection_id()")[0][0]
			frappe.destroy()
			return connection_id, hasattr(frappe.local, "site")

		connection_id, has_site = run_in_thread(worker_thread)
		self.assertFalse(has_site)
		self.assertFalse(connection_is_alive(connection_id))

	def test_destroy_without_connection_can_run_twice(self):
		def worker_thread():
			frappe.init(self.site)
			frappe.destroy()
			frappe.destroy()
			return hasattr(frappe.local, "site")

		self.assertFalse(run_in_thread(worker_thread))

	# Requests

	def test_request_starts_clean_after_previous_request_failed_cleanup(self):
		def worker_thread():
			client = Client(frappe.app.application)
			with self.assertRaises(CleanupFailed):
				self.call(client, "poison_and_break_cleanup")
			left_behind = getattr(frappe.local, "stale_marker", None)
			first = _states[-1]
			second = self.call(client, "probe", stale_connection_id=first["connection_id"]).json["message"]
			return first, left_behind, second

		first, left_behind, second = run_in_thread(worker_thread)
		# the scenario is only meaningful if cleanup really failed
		self.assertEqual(left_behind, POISON)
		self.assertClean(second)
		self.assertEqual(second["user"], "Guest")
		self.assertIsNone(second["job_method"])
		self.assertEqual(second["app_modules"], sorted(frappe.get_installed_apps()))
		self.assertNotEqual(second["connection_id"], first["connection_id"])
		self.assertFalse(second["stale_connection_alive"], "connection of the failed request leaked")

	def test_user_does_not_leak_into_next_request_after_failed_cleanup(self):
		def worker_thread():
			client = Client(frappe.app.application, use_cookies=False)
			with self.assertRaises(CleanupFailed):
				self.call(client, "poison_and_break_cleanup", auth=self.api_auth)
			first = _states[-1]
			second = self.call(client, "probe").json["message"]
			users = self.call(client, "/api/resource/User")
			return first["user"], second["user"], users.status_code

		first_user, second_user, status = run_in_thread(worker_thread)
		self.assertEqual(first_user, TEST_USER)
		self.assertEqual(second_user, "Guest")
		self.assertEqual(status, 403)

	def test_request_starts_clean_when_thread_context_is_dirty(self):
		"""e.g. code ran in this worker thread outside a request and did not clean up."""

		def worker_thread():
			frappe.init(self.site)
			frappe.connect()
			poison_local()
			connection_id = frappe.db.sql("select connection_id()")[0][0]
			client = Client(frappe.app.application)
			response = self.call(client, "probe", stale_connection_id=connection_id)
			return connection_id, response.json["message"]

		connection_id, state = run_in_thread(worker_thread)
		self.assertClean(state)
		self.assertNotEqual(state["connection_id"], connection_id)
		self.assertFalse(state["stale_connection_alive"])

	def test_sequential_requests_do_not_share_local(self):
		def worker_thread():
			client = Client(frappe.app.application)
			return [self.call(client, "poison_only").json["message"] for _ in range(5)]

		states = run_in_thread(worker_thread)
		for state in states:
			self.assertClean(state)
		self.assertEqual(len({state["connection_id"] for state in states}), len(states))

	def test_request_attributes_survive_init(self):
		"""`init_request` now sets request attributes after `frappe.init` resets `frappe.local`."""

		def worker_thread():
			client = Client(frappe.app.application)
			ajax = self.call(client, "request_info", headers={"X-Requested-With": "XMLHttpRequest"})
			plain = self.call(client, "request_info")
			return ajax.json["message"], plain.json["message"], hasattr(frappe.local, "site")

		ajax, plain, still_initialised = run_in_thread(worker_thread)
		self.assertTrue(ajax["is_ajax"])
		self.assertFalse(plain["is_ajax"])
		self.assertEqual(ajax["path"], f"/api/method/{__name__}.request_info")
		# after_response callbacks ran while the site was still initialised, then destroy ran
		self.assertEqual(_after_response_sites, [self.site, self.site])
		self.assertFalse(still_initialised)

	def test_init_request_uses_request_mode(self):
		def worker_thread():
			client = Client(frappe.app.application)
			with patch("frappe.init", wraps=frappe.init) as init:
				response = self.call(client, "probe")
			return response.status_code, init.call_args_list

		status, calls = run_in_thread(worker_thread)
		self.assertEqual(status, 200)
		self.assertEqual(len(calls), 1)
		self.assertEqual(calls[0].args, (self.site,))
		self.assertEqual(
			calls[0].kwargs, {"sites_path": frappe.app._sites_path, "force": True, "is_request": True}
		)

	def test_unknown_site_does_not_break_next_request(self):
		def worker_thread():
			client = Client(frappe.app.application)
			unknown = self.call(client, "probe", headers={"X-Frappe-Site-Name": "no-such-site.invalid"})
			known = self.call(client, "probe")
			return unknown.status_code, known.status_code, known.json["message"]

		unknown_status, known_status, state = run_in_thread(worker_thread)
		self.assertEqual(unknown_status, 404)
		self.assertEqual(known_status, 200)
		self.assertClean(state)

	# Background jobs

	def test_job_starts_clean_after_previous_job_failed_cleanup(self):
		def worker_thread():
			with self.assertRaises(CleanupFailed):
				self.run_job("job_poison_and_break_cleanup")
			left_behind = getattr(frappe.local, "stale_marker", None)
			first = _states[-1]
			second = self.run_job("job_probe", stale_connection_id=first["connection_id"])
			return first, left_behind, second

		first, left_behind, second = run_in_thread(worker_thread)
		# the scenario is only meaningful if cleanup really failed
		self.assertEqual(left_behind, POISON)
		self.assertClean(second)
		self.assertEqual(second["user"], "Administrator")
		self.assertEqual(second["job_method"], f"{__name__}.job_probe")
		self.assertNotEqual(second["connection_id"], first["connection_id"])
		self.assertFalse(second["stale_connection_alive"], "connection of the failed job leaked")

	def test_job_user_does_not_leak_after_failed_cleanup(self):
		def worker_thread():
			with self.assertRaises(CleanupFailed):
				self.run_job("job_poison_and_break_cleanup", user=TEST_USER)
			return (
				_states[-1]["user"],
				self.run_job("job_probe")["user"],
				self.run_job("job_probe", user="Guest")["user"],
			)

		self.assertEqual(run_in_thread(worker_thread), (TEST_USER, "Administrator", "Guest"))

	def test_job_starts_clean_when_thread_context_is_dirty(self):
		def worker_thread():
			frappe.init(self.site)
			frappe.connect()
			poison_local()
			connection_id = frappe.db.sql("select connection_id()")[0][0]
			return connection_id, self.run_job("job_probe", stale_connection_id=connection_id)

		connection_id, state = run_in_thread(worker_thread)
		self.assertClean(state)
		self.assertNotEqual(state["connection_id"], connection_id)
		self.assertFalse(state["stale_connection_alive"])

	def test_execute_job_uses_job_mode(self):
		def worker_thread():
			with patch("frappe.init", wraps=frappe.init) as init:
				self.run_job("job_probe")
			return init.call_args_list

		calls = run_in_thread(worker_thread)
		self.assertEqual(len(calls), 1)
		self.assertEqual(calls[0].args, (self.site,))
		self.assertEqual(calls[0].kwargs, {"force": True, "is_job": True})

	def test_job_module_map_has_only_installed_apps(self):
		"""Jobs build the module map like requests do: only apps installed on the site."""
		state = run_in_thread(self.run_job, "job_probe")
		self.assertEqual(state["app_modules"], sorted(frappe.get_installed_apps()))

	# Known bug, older than the clean-local change (also in upstream): after a retry, the outer
	# `execute_job` re-inits in `finally` without `frappe.local.job` and fails on `after_job.run()`.
	@unittest.expectedFailure
	def test_retried_job_starts_clean(self):
		state = run_in_thread(self.run_job, "job_retry_once")
		self.assertEqual(len(_states), 2)
		self.assertClean(state)
		self.assertEqual(state["job_method"], f"{__name__}.job_retry_once")

	def test_sync_job_keeps_callers_local(self):
		def worker_thread():
			frappe.init(self.site)
			frappe.connect()
			frappe.local.marker = "caller"
			try:
				self.run_job("job_probe", is_async=False)
				return frappe.local.marker, frappe.local.site
			finally:
				frappe.destroy()

		self.assertEqual(run_in_thread(worker_thread), ("caller", self.site))

	def test_in_process_rq_worker_runs_each_job_with_clean_local(self):
		"""Many jobs in one process and thread, like the no-fork worker (worker pool)."""
		queue = Queue(f"test-local-lifecycle-{frappe.generate_hash(length=8)}", connection=get_redis_conn())
		self.addCleanup(queue.delete, delete_jobs=True)

		def enqueue(method):
			return queue.enqueue_call(
				execute_job,
				kwargs={
					"site": self.site,
					"method": f"{__name__}.{method}",
					"event": None,
					"job_name": method,
					"kwargs": {},
					"user": None,
					"is_async": True,
				},
			)

		broken = enqueue("job_poison_and_break_cleanup")
		probe = enqueue("job_probe_previous")
		# SimpleWorker needs the main thread (SIGALRM job timeouts). Run it in a copied context
		# so the jobs do not touch this test's `frappe.local`.
		worker = SimpleWorker([queue], connection=queue.connection)
		contextvars.copy_context().run(worker.work, burst=True)

		self.assertEqual(broken.get_status(refresh=True), "failed")
		self.assertEqual(probe.get_status(refresh=True), "finished")
		state = probe.return_value()
		self.assertClean(state)
		self.assertFalse(state["stale_connection_alive"], "connection of the failed job leaked")
		self.assertEqual(frappe.local.site, self.site)

	# Existing callers of `frappe.init(force=True)`

	def test_switch_site_leaves_a_working_connection(self):
		def worker_thread():
			frappe.init(self.site)
			frappe.connect()
			frappe.local.marker = "before-switch"
			with self.switch_site(self.site):
				inside = frappe.db.sql("select 1")[0][0], hasattr(frappe.local, "marker")
			after = frappe.db.sql("select 1")[0][0], frappe.local.site
			frappe.destroy()
			return inside, after

		self.assertEqual(run_in_thread(worker_thread), ((1, False), (1, self.site)))
