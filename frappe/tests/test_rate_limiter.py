# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import time
from functools import partial

from werkzeug.wrappers import Response

import frappe
import frappe.rate_limiter
from frappe.rate_limiter import RateLimiter, rate_limit
from frappe.tests import IntegrationTestCase
from frappe.utils import cint, set_request


class TestRateLimiter(IntegrationTestCase):
	def test_apply_with_limit(self):
		frappe.conf.rate_limit = {"window": 86400, "limit": 1}
		frappe.rate_limiter.apply()

		self.assertTrue(hasattr(frappe.local, "rate_limiter"))
		self.assertIsInstance(frappe.local.rate_limiter, RateLimiter)

		frappe.cache.delete(frappe.local.rate_limiter.key)
		delattr(frappe.local, "rate_limiter")

	def test_apply_without_limit(self):
		frappe.conf.rate_limit = None
		frappe.rate_limiter.apply()

		self.assertFalse(hasattr(frappe.local, "rate_limiter"))

	def test_respond_over_limit(self):
		limiter = RateLimiter(1, 86400)
		time.sleep(1)
		limiter.update()

		frappe.conf.rate_limit = {"window": 86400, "limit": 1}
		self.assertRaises(frappe.TooManyRequestsError, frappe.rate_limiter.apply)
		frappe.rate_limiter.update()

		response = frappe.rate_limiter.respond()

		self.assertIsInstance(response, Response)
		self.assertEqual(response.status_code, 429)

		headers = frappe.local.rate_limiter.headers()
		self.assertIn("Retry-After", headers)
		self.assertIn("X-RateLimit-Reset", headers)
		self.assertIn("X-RateLimit-Limit", headers)
		self.assertIn("X-RateLimit-Remaining", headers)
		self.assertTrue(int(headers["X-RateLimit-Reset"]) <= 86400)
		self.assertEqual(int(headers["X-RateLimit-Limit"]), 1000000)
		self.assertEqual(int(headers["X-RateLimit-Remaining"]), 0)

		frappe.cache.delete(limiter.key)
		frappe.cache.delete(frappe.local.rate_limiter.key)
		delattr(frappe.local, "rate_limiter")

	def test_respond_under_limit(self):
		frappe.conf.rate_limit = {"window": 86400, "limit": 0.01}
		frappe.rate_limiter.apply()
		frappe.rate_limiter.update()
		response = frappe.rate_limiter.respond()
		self.assertEqual(response, None)

		frappe.cache.delete(frappe.local.rate_limiter.key)
		delattr(frappe.local, "rate_limiter")

	def test_headers_under_limit(self):
		frappe.conf.rate_limit = {"window": 86400, "limit": 1}
		frappe.rate_limiter.apply()
		frappe.rate_limiter.update()
		headers = frappe.local.rate_limiter.headers()
		self.assertNotIn("Retry-After", headers)
		self.assertIn("X-RateLimit-Reset", headers)
		self.assertTrue(int(headers["X-RateLimit-Reset"] < 86400))
		self.assertEqual(int(headers["X-RateLimit-Limit"]), 1000000)
		self.assertEqual(int(headers["X-RateLimit-Remaining"]), 1000000)

		frappe.cache.delete(frappe.local.rate_limiter.key)
		delattr(frappe.local, "rate_limiter")

	def test_reject_over_limit(self):
		limiter = RateLimiter(0.01, 86400)
		time.sleep(0.01)
		limiter.update()

		limiter = RateLimiter(0.01, 86400)
		self.assertRaises(frappe.TooManyRequestsError, limiter.apply)

		frappe.cache.delete(limiter.key)

	def test_do_not_reject_under_limit(self):
		limiter = RateLimiter(0.01, 86400)
		time.sleep(0.01)
		limiter.update()

		limiter = RateLimiter(0.02, 86400)
		self.assertEqual(limiter.apply(), None)

		frappe.cache.delete(limiter.key)

	def test_update_method(self):
		limiter = RateLimiter(0.01, 86400)
		time.sleep(0.01)
		limiter.update()

		self.assertEqual(limiter.duration, cint(frappe.cache.get(limiter.key)))

		frappe.cache.delete(limiter.key)

	def test_window_expires(self):
		limiter = RateLimiter(1000, 1)
		self.assertTrue(frappe.cache.exists(limiter.key, shared=True))
		limiter.update()
		self.assertTrue(frappe.cache.exists(limiter.key, shared=True))
		time.sleep(1.1)
		self.assertFalse(frappe.cache.exists(limiter.key, shared=True))
		frappe.cache.delete(limiter.key)


@rate_limit(limit=2, seconds=60)
def _limited_a():
	return "a"


@rate_limit(limit=2, seconds=60)
def _limited_b():
	return "b"


@rate_limit(limit=2, seconds=60, user_based=True)
def _limited_user_based():
	return "user-based"


@rate_limit(limit=2, seconds=60, user_based=True, ip_based=False)
def _limited_user_based_no_ip():
	return "user-based-no-ip"


@rate_limit(limit=1, seconds=60, key="priority", user_based=True)
def _limited_user_based_with_key():
	return "keyed"


class TestRateLimitDecorator(IntegrationTestCase):
	def setUp(self):
		request, request_ip, user = (
			getattr(frappe.local, "request", None),
			getattr(frappe.local, "request_ip", None),
			getattr(frappe.session, "user", None),
		)
		self.addCleanup(setattr, frappe.local, "request", request)
		self.addCleanup(setattr, frappe.local, "request_ip", request_ip)
		self.addCleanup(frappe.set_user, user or "Administrator")
		self.addCleanup(frappe.cache.delete_keys, "rl:")
		self.addCleanup(frappe.form_dict.pop, "cmd", None)

		set_request(method="GET", path="/api/method/ping")
		frappe.local.request_ip = "127.0.0.1"

	def test_limit_is_shared_across_api_versions(self):
		# v1 sets `cmd`, v2 does not, the same endpoint must share one counter
		frappe.form_dict.cmd = "frappe.tests.test_rate_limiter._limited_a"
		_limited_a()

		frappe.form_dict.cmd = None
		_limited_a()

		self.assertRaises(frappe.RateLimitExceededError, _limited_a)

	def test_callable_without_dotted_path(self):
		# Server Scripts rate limit a `functools.partial`, which has no qualified name
		fn = rate_limit(limit=1, seconds=60, endpoint="server_script:x")(partial(lambda: "x"))
		fn()
		self.assertRaises(frappe.RateLimitExceededError, fn)

	def test_limit_is_not_shared_across_endpoints(self):
		frappe.form_dict.cmd = None
		_limited_a()
		_limited_a()
		self.assertRaises(frappe.RateLimitExceededError, _limited_a)

		self.assertEqual(_limited_b(), "b")

	def test_authenticated_user_shares_counter_across_ips(self):
		frappe.set_user("Administrator")

		frappe.local.request_ip = "10.0.0.1"
		_limited_user_based()

		frappe.local.request_ip = "10.0.0.2"
		_limited_user_based()

		self.assertRaises(frappe.RateLimitExceededError, _limited_user_based)

	def test_different_authenticated_users_do_not_share_counter(self):
		frappe.set_user("Administrator")
		_limited_user_based()
		_limited_user_based()

		frappe.set_user("someone-else@example.com")
		self.assertEqual(_limited_user_based(), "user-based")

	def test_guest_falls_back_to_ip_when_ip_based(self):
		frappe.set_user("Guest")
		frappe.local.request_ip = "10.0.0.5"

		_limited_user_based()
		_limited_user_based()
		self.assertRaises(frappe.RateLimitExceededError, _limited_user_based)

		frappe.local.request_ip = "10.0.0.6"
		self.assertEqual(_limited_user_based(), "user-based")

	def test_guests_share_one_pooled_bucket_when_ip_based_is_false(self):
		frappe.set_user("Guest")

		frappe.local.request_ip = "10.0.0.7"
		_limited_user_based_no_ip()

		frappe.local.request_ip = "10.0.0.8"
		_limited_user_based_no_ip()

		self.assertRaises(frappe.RateLimitExceededError, _limited_user_based_no_ip)

	def test_user_based_with_key_is_further_scoped_by_key(self):
		self.addCleanup(frappe.form_dict.pop, "priority", None)
		frappe.set_user("Administrator")

		frappe.form_dict.priority = "high"
		_limited_user_based_with_key()
		self.assertRaises(frappe.RateLimitExceededError, _limited_user_based_with_key)

		# same user, different key value -> separate bucket
		frappe.form_dict.priority = "low"
		self.assertEqual(_limited_user_based_with_key(), "keyed")

	def test_requires_an_identity_source(self):
		fn = rate_limit(limit=1, seconds=60, ip_based=False, user_based=False)(lambda: "x")
		self.assertRaises(frappe.ValidationError, fn)
