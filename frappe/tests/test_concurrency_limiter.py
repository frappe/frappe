# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import contextlib
import contextvars
import os
import sys
import tempfile
import threading
import types
from unittest.mock import MagicMock, patch

from gunicorn.config import Workers

import frappe
from frappe.concurrency_limiter import (
	WebTierSettings,
	_default_limit,
	concurrent_limit,
	web_tier_concurrency,
	web_tier_settings,
)
from frappe.exceptions import ServiceUnavailableError
from frappe.tests import IntegrationTestCase


def _key(fn):
	"""Reconstruct the Redis key that concurrent_limit uses for a decorated function."""
	return f"concurrency:{fn.__module__}.{fn.__qualname__}"


def _cleanup(fn):
	key = _key(fn)
	frappe.cache.delete_value([key, f"{key}:capacity"], shared=True)


class TestConcurrentLimit(IntegrationTestCase):
	def test_bypassed_outside_request_context(self):
		"""Decorator is a no-op outside HTTP request context (background jobs, CLI, tests).
		Even limit=0 must not reject."""
		calls = []

		@concurrent_limit(limit=0)
		def fn():
			calls.append(True)

		saved = getattr(frappe.local, "request", None)
		if saved:
			del frappe.local.request

		try:
			fn()  # must not raise despite limit=0
		finally:
			if saved:
				frappe.local.request = saved

		self.assertEqual(calls, [True])

	def test_pool_exhaustion_raises_503_with_retry_after_header(self):
		"""When all slots are occupied, the next request raises ServiceUnavailableError
		(HTTP 503) immediately with wait_timeout=0. The Retry-After response header must be set."""
		in_fn = threading.Event()
		proceed = threading.Event()

		@concurrent_limit(limit=1, wait_timeout=0)
		def fn():
			in_fn.set()
			proceed.wait()

		ctx = contextvars.copy_context()

		def hold_slot():
			frappe.local.request = frappe._dict()
			fn()

		t = threading.Thread(target=ctx.run, args=(hold_slot,))
		t.start()
		self.assertTrue(in_fn.wait(timeout=5), "Thread did not acquire the slot in time")

		mock_headers = MagicMock()
		saved_headers = getattr(frappe.local, "response_headers", None)
		try:
			frappe.local.request = frappe._dict()
			frappe.local.response_headers = mock_headers
			with self.assertRaises(ServiceUnavailableError) as exc_ctx:
				fn()
			self.assertEqual(exc_ctx.exception.http_status_code, 503)
			mock_headers.set.assert_called_once_with("Retry-After", "1")  # max(1, wait_timeout=0)
		finally:
			proceed.set()
			t.join(timeout=5)
			del frappe.local.request
			frappe.local.response_headers = saved_headers
			_cleanup(fn)

	def test_token_released_on_success(self):
		"""A token is returned to the pool after a successful call,
		so subsequent calls can acquire it without hitting a 503."""

		@concurrent_limit(limit=1, wait_timeout=0)
		def fn():
			pass

		try:
			frappe.local.request = frappe._dict()
			fn()
			fn()  # should not raise ServiceUnavailableError since the token was released after the first call
		finally:
			del frappe.local.request
			_cleanup(fn)

	def test_token_released_on_exception(self):
		"""A token is returned to the pool even when the wrapped function raises,
		so subsequent calls can proceed with their own application error, not a 503."""

		@concurrent_limit(limit=1, wait_timeout=0)
		def fn():
			raise ValueError("boom")

		try:
			frappe.local.request = frappe._dict()
			with self.assertRaises(ValueError):
				fn()
			# Second call must raise ValueError (application error), not
			# ServiceUnavailableError — which would indicate the token was leaked.
			with self.assertRaises(ValueError):
				fn()
		finally:
			del frappe.local.request
			_cleanup(fn)

	def test_self_heals_after_capacity_key_expiry(self):
		"""After the capacity key expires (simulating crashed workers + TTL),
		the pool re-initializes to full capacity so new requests succeed."""

		@concurrent_limit(limit=1, wait_timeout=0)
		def fn():
			pass

		key = _key(fn)
		try:
			frappe.local.request = frappe._dict()
			fn()  # initializes the pool via the decorator

			# Simulate all tokens being leaked (workers crashed mid-request)
			# by draining the pool without returning tokens.
			while frappe.cache.lpop(key, shared=True):
				pass

			# Simulate capacity key TTL expiry.
			frappe.cache.delete_value(f"{key}:capacity", shared=True)

			# Self-heal: next request must re-initialize the pool and succeed.
			fn()  # must not raise ServiceUnavailableError
		finally:
			del frappe.local.request
			_cleanup(fn)

	def test_fails_open_when_redis_unavailable(self):
		"""When Redis is unavailable during acquire, the request proceeds normally
		(fail-open) rather than raising ServiceUnavailableError."""
		calls = []

		@concurrent_limit(limit=1, wait_timeout=0)
		def fn():
			calls.append(True)

		try:
			frappe.local.request = frappe._dict()
			with patch.object(frappe.cache, "lpop", side_effect=Exception("Redis down")):
				fn()  # must not raise
		finally:
			del frappe.local.request
			_cleanup(fn)

		self.assertEqual(calls, [True])


class TestWebTierConcurrency(IntegrationTestCase):
	@contextlib.contextmanager
	def _server(self, argv, server_software="gunicorn/23.0.0", cwd=None):
		"""Run the body as if this process were a gunicorn worker started with *argv* in *cwd*."""
		env = {"SERVER_SOFTWARE": server_software} if server_software else {}
		saved_cwd, saved_config = os.getcwd(), sys.modules.pop("__config__", None)
		web_tier_settings.cache_clear()
		try:
			with (
				tempfile.TemporaryDirectory() as empty_dir,
				patch.object(sys, "argv", argv),
				patch.dict(os.environ, env, clear=False),
			):
				os.environ.pop("GUNICORN_CMD_ARGS", None)
				if not server_software:
					os.environ.pop("SERVER_SOFTWARE", None)
				os.chdir(cwd or empty_dir)
				try:
					yield
				finally:
					os.chdir(saved_cwd)
		finally:
			sys.modules.pop("__config__", None)
			if saved_config:
				sys.modules["__config__"] = saved_config
			web_tier_settings.cache_clear()

	@contextlib.contextmanager
	def _config_file(self, content):
		with tempfile.TemporaryDirectory() as tmp:
			path = os.path.join(tmp, "gunicorn.conf.py")
			with open(path, "w") as f:
				f.write(content)
			yield path

	def test_no_limit_without_a_worker_pool(self):
		"""The development server starts a thread per request, so there is no pool to protect."""
		with self._server(["bench", "serve"], server_software=None):
			self.assertIsNone(web_tier_concurrency())
			self.assertIsNone(_default_limit())

	def test_reads_workers_and_threads_from_the_gunicorn_command_line(self):
		"""Workers are forked, so sys.argv in a worker is the master's command line."""
		with self._server(["gunicorn", "-w", "3", "--threads", "4", "frappe.app:application"]):
			self.assertEqual(web_tier_concurrency(), 12)
			self.assertEqual(_default_limit(), 6)

	def test_reads_the_flag_equals_value_form(self):
		with self._server(["gunicorn", "--workers=2", "--threads=2", "frappe.app:application"]):
			self.assertEqual(web_tier_concurrency(), 4)

	def test_threads_default_to_one(self):
		with self._server(["gunicorn", "-w", "5", "frappe.app:application"]):
			self.assertEqual(web_tier_concurrency(), 5)
			self.assertEqual(_default_limit(), 2)

	def test_limit_is_at_least_one(self):
		with self._server(["gunicorn", "-w", "1", "frappe.app:application"]):
			self.assertEqual(_default_limit(), 1)

	def test_reads_the_config_file(self):
		"""Frappe Cloud starts gunicorn with ``-c gunicorn.conf.py`` and no ``-w`` or ``--threads``."""
		with self._config_file("workers = 8\nthreads = 4\n") as path:
			with self._server(["gunicorn", "-c", path, "frappe.app:application"]):
				self.assertEqual(web_tier_concurrency(), 32)
				self.assertEqual(_default_limit(), 16)

	def test_reads_the_default_config_file(self):
		"""Gunicorn loads ./gunicorn.conf.py when no config file is named."""
		with self._config_file("workers = 3\nthreads = 2\n") as path:
			with self._server(["gunicorn", "frappe.app:application"], cwd=os.path.dirname(path)):
				self.assertEqual(web_tier_concurrency(), 6)

	def test_reuses_the_config_module_the_master_loaded(self):
		"""A worker must not run the config file again, nor fail when the master's chdir moved it."""
		master_config = types.ModuleType("__config__")
		master_config.workers, master_config.threads = 8, 4
		with self._config_file("raise RuntimeError\n") as path:
			with self._server(["gunicorn", "-c", path, "frappe.app:application"]):
				sys.modules["__config__"] = master_config
				self.assertEqual(web_tier_concurrency(), 32)

	def test_reads_gunicorn_cmd_args(self):
		env = {"GUNICORN_CMD_ARGS": "--workers 3 --threads 3"}
		with self._server(["gunicorn", "frappe.app:application"]), patch.dict(os.environ, env):
			self.assertEqual(web_tier_concurrency(), 9)

	def test_reads_the_config_file_named_in_gunicorn_cmd_args(self):
		with self._config_file("workers = 5\nthreads = 2\n") as path:
			env = {"GUNICORN_CMD_ARGS": f"-c {path}"}
			with self._server(["gunicorn", "frappe.app:application"]), patch.dict(os.environ, env):
				self.assertEqual(web_tier_concurrency(), 10)

	def test_settings_override_in_gunicorn_order(self):
		"""The command line beats GUNICORN_CMD_ARGS, which beats the config file."""
		with self._config_file("workers = 8\nthreads = 4\n") as path:
			env = {"GUNICORN_CMD_ARGS": "--threads 2"}
			with (
				self._server(["gunicorn", "-c", path, "-w", "3", "frappe.app:application"]),
				patch.dict(os.environ, env),
			):
				self.assertEqual(web_tier_concurrency(), 6)

	def test_uses_gunicorn_defaults(self):
		"""Gunicorn's default worker count is WEB_CONCURRENCY, read when gunicorn.config is imported."""
		with self._server(["gunicorn", "frappe.app:application"]), patch.object(Workers, "default", 4):
			self.assertEqual(web_tier_concurrency(), 4)

	def test_no_limit_when_settings_cannot_be_resolved(self):
		"""A launcher whose own command line is not gunicorn's, so no size is guessed."""
		with self._server(["run_server.py", "--port", "8000"]):
			self.assertIsNone(web_tier_concurrency())
			self.assertIsNone(_default_limit())

		with self._config_file("raise RuntimeError\n") as path:
			with self._server(["gunicorn", "-c", path, "frappe.app:application"]):
				self.assertIsNone(web_tier_concurrency())

	def test_reads_timeouts(self):
		with self._config_file("timeout = 120\n") as path:
			with self._server(["gunicorn", "-c", path, "--graceful-timeout", "45", "frappe.app:application"]):
				settings = web_tier_settings()
				self.assertEqual((settings.timeout, settings.graceful_timeout), (120, 45))

	def test_settings_default_to_gunicorn_defaults(self):
		with self._server(["gunicorn", "frappe.app:application"]), patch.object(Workers, "default", 1):
			self.assertEqual(web_tier_settings(), WebTierSettings(1, 1, 30, 30))

	def test_no_settings_outside_gunicorn(self):
		with self._server(["bench", "serve"], server_software=None):
			self.assertIsNone(web_tier_settings())

		with self._server(["run_server.py", "--port", "8000"]):
			self.assertIsNone(web_tier_settings())

	def test_pool_is_skipped_when_there_is_no_limit(self):
		"""A request on the development server must not touch the semaphore."""
		calls = []

		@concurrent_limit()
		def fn():
			calls.append(True)

		try:
			frappe.local.request = frappe._dict()
			with self._server(["bench", "serve"], server_software=None):
				with patch.object(frappe.cache, "lpop", side_effect=AssertionError("semaphore used")):
					fn()
		finally:
			del frappe.local.request

		self.assertEqual(calls, [True])
