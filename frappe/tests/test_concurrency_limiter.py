# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import contextvars
import threading
from unittest.mock import MagicMock, patch

import frappe
from frappe.concurrency_limiter import concurrent_limit
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
